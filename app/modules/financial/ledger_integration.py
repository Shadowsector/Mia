"""Financial Ledger Integration - Integration with 1C/ERP for real financial data.

This module provides integration with financial systems (1C, ERP) to get
real payment data, burn rate calculations, and cash flow analysis.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class FinancialLedgerIntegration:
    """
    Integration with financial systems (1C, ERP).
    
    Provides real financial data for accurate burn rate calculations
    and Health Score assessment.
    """
    
    def __init__(self, integration_type: str = "mock"):
        """
        Initialize Financial Ledger Integration.

        Args:
            integration_type: Type of integration:
                - "mock": deterministic demo data;
                - "local": read real data from the local SQLite `invoices` table;
                - "1c" / "erp": HTTP connector to an external system (see `connect`).
        """
        self.integration_type = integration_type
        self.connection = None
        self.config: Dict[str, Any] = {}

        if integration_type == "mock":
            logger.info("Financial Ledger Integration initialized in MOCK mode")
        elif integration_type == "local":
            logger.info("Financial Ledger Integration initialized in LOCAL (SQLite) mode")
        else:
            logger.info(
                f"Financial Ledger Integration initialized for '{integration_type}' "
                f"HTTP mode (call connect() with config before use)"
            )

    def connect(self, config: Dict[str, Any]) -> bool:
        """
        Connect to financial system.

        Args:
            config: Connection configuration. For HTTP integrations ("1c"/"erp"):
                {"base_url": "...", "token": "...", "timeout": 10}

        Returns:
            True if successful
        """
        if self.integration_type == "mock":
            logger.info("Mock connection successful")
            return True

        if self.integration_type == "local":
            try:
                from app.modules.storage.database import get_db_connection

                with get_db_connection() as conn:
                    conn.execute("SELECT 1").fetchone()
                self.connection = {"type": "sqlite"}
                logger.info("Local SQLite ledger connection successful")
                return True
            except Exception as e:
                logger.error(f"Local ledger connection failed: {e}")
                return False

        base_url = (config or {}).get("base_url")
        if not base_url:
            logger.warning(f"{self.integration_type} connection requires 'base_url'")
            return False

        try:
            import requests

            timeout = (config or {}).get("timeout", 10)
            headers = {}
            if config.get("token"):
                headers["Authorization"] = f"Bearer {config['token']}"

            response = requests.get(f"{base_url}/health", headers=headers, timeout=timeout)
            if response.status_code >= 400:
                logger.warning(
                    f"{self.integration_type} health-check returned {response.status_code}"
                )
                return False

            self.config = dict(config)
            self.connection = {"type": "http", "base_url": base_url, "headers": headers}
            logger.info(f"Connected to {self.integration_type} at {base_url}")
            return True
        except Exception as e:
            logger.error(f"Connection to {self.integration_type} failed: {e}")
            return False

    def _http_get(self, path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Выполнить GET-запрос к внешней финансовой системе."""
        if not self.connection or self.connection.get("type") != "http":
            logger.warning(f"{self.integration_type}: not connected")
            return []

        try:
            import requests

            url = f"{self.connection['base_url']}{path}"
            response = requests.get(
                url,
                params=params,
                headers=self.connection.get("headers", {}),
                timeout=self.config.get("timeout", 10),
            )
            if response.status_code >= 400:
                logger.warning(f"{self.integration_type} {path} returned {response.status_code}")
                return []

            data = response.json()
            if isinstance(data, dict):
                data = data.get("items") or data.get("data") or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"{self.integration_type} {path} failed: {e}")
            return []

    def get_payments(self, object_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get payments for an object within date range.

        Args:
            object_id: Object ID
            start_date: Start date
            end_date: End date

        Returns:
            List of payments
        """
        if self.integration_type == "mock":
            # Return mock data
            return self._get_mock_payments(object_id, start_date, end_date)

        if self.integration_type == "local":
            return self._get_local_records(
                object_id, start_date, end_date,
                statuses=(PaymentStatus.PAID.value, PaymentStatus.PARTIALLY_PAID.value),
            )

        return self._http_get("/payments", {
            "object_id": object_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        })
    
    def _get_mock_payments(self, object_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get mock payment data for testing."""
        mock_payments = [
            {
                'payment_id': f"PAY-{object_id}-001",
                'object_id': object_id,
                'amount': 500000.0,
                'date': (start_date + timedelta(days=5)).isoformat(),
                'status': PaymentStatus.PAID.value,
                'description': 'Предоплата'
            },
            {
                'payment_id': f"PAY-{object_id}-002",
                'object_id': object_id,
                'amount': 300000.0,
                'date': (start_date + timedelta(days=20)).isoformat(),
                'status': PaymentStatus.PAID.value,
                'description': 'Промежуточный платеж'
            }
        ]
        
        return mock_payments
    
    def _get_local_records(
        self,
        object_id: str,
        start_date: datetime,
        end_date: datetime,
        statuses: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """Прочитать финансовые записи из локальной таблицы `invoices`."""
        try:
            from app.modules.storage.database import get_db_connection

            query = (
                "SELECT invoice_id, object_id, amount, date, status, description "
                "FROM invoices WHERE object_id = ? AND date >= ? AND date <= ?"
            )
            params: List[Any] = [object_id, start_date.isoformat(), end_date.isoformat()]

            if statuses:
                placeholders = ",".join("?" for _ in statuses)
                query += f" AND status IN ({placeholders})"
                params.extend(statuses)

            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Local ledger read failed for {object_id}: {e}")
            return []

    def get_invoices(self, object_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get invoices for an object within date range.

        Args:
            object_id: Object ID
            start_date: Start date
            end_date: End date

        Returns:
            List of invoices
        """
        if self.integration_type == "mock":
            return self._get_mock_invoices(object_id, start_date, end_date)

        if self.integration_type == "local":
            return self._get_local_records(object_id, start_date, end_date)

        return self._http_get("/invoices", {
            "object_id": object_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        })
    
    def _get_mock_invoices(self, object_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get mock invoice data for testing."""
        mock_invoices = [
            {
                'invoice_id': f"INV-{object_id}-001",
                'object_id': object_id,
                'amount': 750000.0,
                'date': (start_date + timedelta(days=10)).isoformat(),
                'status': PaymentStatus.PAID.value,
                'description': 'Счёт за материалы'
            },
            {
                'invoice_id': f"INV-{object_id}-002",
                'object_id': object_id,
                'amount': 200000.0,
                'date': (start_date + timedelta(days=25)).isoformat(),
                'status': PaymentStatus.PENDING.value,
                'description': 'Счёт за работы'
            }
        ]
        
        return mock_invoices
    
    def calculate_burn_rate(self, object_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Calculate burn rate based on actual payments.
        
        Args:
            object_id: Object ID
            start_date: Start date
            end_date: End date
            
        Returns:
            Burn rate calculation
        """
        # Get payments
        payments = self.get_payments(object_id, start_date, end_date)
        
        # Calculate total paid
        total_paid = sum(p['amount'] for p in payments if p['status'] == PaymentStatus.PAID.value)
        
        # Calculate days elapsed
        days_elapsed = (end_date - start_date).days
        
        if days_elapsed > 0:
            daily_burn_rate = total_paid / days_elapsed
        else:
            daily_burn_rate = 0
        
        return {
            'object_id': object_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_paid': total_paid,
            'days_elapsed': days_elapsed,
            'daily_burn_rate': daily_burn_rate,
            'payment_count': len(payments)
        }
    
    def get_cash_flow(self, object_id: str, months: int = 6) -> Dict[str, Any]:
        """
        Get cash flow analysis for an object.
        
        Args:
            object_id: Object ID
            months: Number of months to analyze
            
        Returns:
            Cash flow analysis
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        payments = self.get_payments(object_id, start_date, end_date)
        invoices = self.get_invoices(object_id, start_date, end_date)
        
        # Group by month
        monthly_data = {}
        
        for payment in payments:
            month = payment['date'][:7]  # YYYY-MM
            if month not in monthly_data:
                monthly_data[month] = {'inflow': 0, 'outflow': 0}
            monthly_data[month]['inflow'] += payment['amount']
        
        for invoice in invoices:
            month = invoice['date'][:7]
            if month not in monthly_data:
                monthly_data[month] = {'inflow': 0, 'outflow': 0}
            monthly_data[month]['outflow'] += invoice['amount']
        
        return {
            'object_id': object_id,
            'months_analyzed': months,
            'monthly_data': monthly_data,
            'total_inflow': sum(d['inflow'] for d in monthly_data.values()),
            'total_outflow': sum(d['outflow'] for d in monthly_data.values()),
            'net_cash_flow': sum(d['inflow'] - d['outflow'] for d in monthly_data.values())
        }
    
    def sync_with_ledger(self, object_id: str) -> bool:
        """
        Sync financial data with local ledger.
        
        Args:
            object_id: Object ID
            
        Returns:
            True if successful
        """
        try:
            from app.modules.storage.database import get_db_connection
            
            # Get financial data from external system
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)  # Last 90 days
            
            payments = self.get_payments(object_id, start_date, end_date)
            invoices = self.get_invoices(object_id, start_date, end_date)
            
            # Sync to local database
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Sync payments
                for payment in payments:
                    cursor.execute("""
                        INSERT OR REPLACE INTO invoices (
                            invoice_id, object_id, amount, date, status, description
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        payment['payment_id'],
                        payment['object_id'],
                        payment['amount'],
                        payment['date'],
                        payment['status'],
                        payment['description']
                    ))
                
                logger.info(f"Synced {len(payments)} payments for {object_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error syncing with ledger: {e}")
            return False


class FinancialHealthAnalyzer:
    """
    Analyze financial health based on real payment data.
    
    Integrates with Health Score Engine to provide accurate
    financial risk assessment.
    """
    
    def __init__(self, financial_integration: FinancialLedgerIntegration):
        """
        Initialize Financial Health Analyzer.
        
        Args:
            financial_integration: Financial Ledger Integration instance
        """
        self.financial_integration = financial_integration
    
    def analyze_cash_gap(self, object_id: str, budget: float) -> Dict[str, Any]:
        """
        Analyze cash gap (difference between budget and actual spending).
        
        Args:
            object_id: Object ID
            budget: Total budget
            
        Returns:
            Cash gap analysis
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        burn_rate = self.financial_integration.calculate_burn_rate(object_id, start_date, end_date)
        
        total_paid = burn_rate['total_paid']
        remaining_budget = budget - total_paid
        
        cash_gap_ratio = total_paid / budget if budget > 0 else 0
        
        # Determine risk level
        if cash_gap_ratio > 0.9:
            risk_level = 'critical'
        elif cash_gap_ratio > 0.75:
            risk_level = 'high'
        elif cash_gap_ratio > 0.5:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'object_id': object_id,
            'budget': budget,
            'total_paid': total_paid,
            'remaining_budget': remaining_budget,
            'cash_gap_ratio': cash_gap_ratio,
            'risk_level': risk_level,
            'daily_burn_rate': burn_rate['daily_burn_rate']
        }
    
    def predict_budget_exhaustion(self, object_id: str, budget: float) -> Optional[datetime]:
        """
        Predict when budget will be exhausted based on burn rate.
        
        Args:
            object_id: Object ID
            budget: Total budget
            
        Returns:
            Predicted exhaustion date or None
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Last 30 days
        
        burn_rate = self.financial_integration.calculate_burn_rate(object_id, start_date, end_date)
        daily_burn_rate = burn_rate['daily_burn_rate']
        
        if daily_burn_rate <= 0:
            return None
        
        days_to_exhaustion = budget / daily_burn_rate
        exhaustion_date = end_date + timedelta(days=days_to_exhaustion)
        
        return exhaustion_date


if __name__ == "__main__":
    # Test Financial Ledger Integration
    logging.basicConfig(level=logging.INFO)
    
    # Initialize with mock integration
    financial_integration = FinancialLedgerIntegration(integration_type="mock")
    
    # Test burn rate calculation
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    burn_rate = financial_integration.calculate_burn_rate("TEST-001", start_date, end_date)
    print(f"Burn rate: {burn_rate}")
    
    # Test cash flow
    cash_flow = financial_integration.get_cash_flow("TEST-001", months=3)
    print(f"Cash flow: {cash_flow}")
    
    # Test financial health analyzer
    analyzer = FinancialHealthAnalyzer(financial_integration)
    
    cash_gap = analyzer.analyze_cash_gap("TEST-001", budget=2000000.0)
    print(f"Cash gap: {cash_gap}")
    
    exhaustion_date = analyzer.predict_budget_exhaustion("TEST-001", budget=2000000.0)
    print(f"Predicted exhaustion: {exhaustion_date}")
