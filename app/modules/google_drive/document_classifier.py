"""Improved document classifier with focused patterns"""

import re
from typing import Dict, List, Any

class ImprovedDocumentClassifier:
    """Classifier with focused patterns for construction documents"""
    
    # CAD sidecar/service extensions — not real documents
    CAD_SERVICE_EXTS = {
        'shx', 'bak', 'sig', 'sor', 'tmp', 'log', 'pc3', 'ctb',
        'dwl', 'dwl2', 'lsp', 'vsz', 'fmp', 'err',
    }
    CAD_EXTS = {'dwg', 'dxf', 'dwf'}
    
    # Focused patterns for construction documents (requires word boundaries)
    PATTERNS = {
        # Document types
        'rd': [
            r'\bрд\b', r'\bрабочая документация\b', r'\bрабочий документ\b',
            r'\bрд\s*-\b', r'\b_\s*рд\b', r'\b\s*рд\s*\.'
        ],
        'sps': [
            r'\bспс\b', r'\bстроительные проектные решения\b',
            r'\bспс\s*-\b', r'\b_\s*спс\b'
        ],
        'pzu': [
            r'\bпзу\b', r'\bпроектные решения узлов\b',
            r'\bпзу\s*-\b', r'\b_\s*пзу\b'
        ],
        'tu': [
            r'\bту\b', r'\bтехнические условия\b',
            r'\bту\s*-\b', r'\b_\s*ту\b'
        ],
        'nss': [
            r'\bнсс\b', r'\bнаружные сооружения связи\b',
            r'\bнсс\s*-\b', r'\b_\s*нсс\b'
        ],
        'id': [
            r'\bид\b', r'\bисходные данные\b', r'\bтехническое задание\b',
            r'\bид\s*-\b', r'\b_\s*ид\b'
        ],
        'gp': [
            r'\bгп\b', r'\bгенеральный план\b',
            r'\bгп\s*-\b', r'\b_\s*гп\b'
        ],
        'ops': [
            r'\bопс\b', r'\bстройгенплан\b',
            r'\bопс\s*-\b', r'\b_\s*опс\b'
        ],
        'pos': [
            r'\bпос\b', r'\bпроект организации строительства\b',
            r'\bпос\s*-\b', r'\b_\s*пос\b'
        ],
        'pir': [
            r'\bпир\b', r'\bпроектно-изыскательские работы\b',
            r'\bпир\s*-\b', r'\b_\s*пир\b'
        ],
        'act': [
            r'\bакт\b', r'\bакты\b',
            r'\bакт\s*[0-9]\b', r'\bакт\s*[а-я]\b'
        ],
        'spravka': [
            r'\bсправка\b', r'\bсправки\b',
            r'\bсправка\s*[0-9]\b'
        ],
        'passport': [
            r'\bпаспорт\b', r'\bпаспорта\b',
            r'\bпаспорт\s*[а-я]\b', r'\bтехпаспорт\b',
            r'\bтех\s*паспорт\b', r'\bpassport\b'
        ],
        'smeta': [
            r'\bсмета\b', r'\bсметы\b',
            r'\bсмета\s*[0-9]\b'
        ],
        'dogovor': [
            r'\bдоговор\b', r'\bсоглашение\b',
            r'\bдоговор\s*[0-9]\b', r'\bсоглашение\s*[0-9]\b'
        ],
        'schet': [
            r'\bсчет\b', r'\bнакладная\b', r'\bупд\b',
            r'\bсчет\s*[0-9]\b'
        ],
        'invoice': [
            r'\binvoice\b', r'\binvoice_\b'
        ],
        'estimate': [
            r'\bestimate\b', r'\bestimate_\b'
        ],
        'project': [
            r'\bпроект\b', r'\bproject\b',
            r'\bпроект\s*[а-я]\b'
        ],
        'zamechaniya': [
            r'\bзамечание\b', r'\bзамечания\b', r'\bотзыв\b'
        ],
        'soglasovanie': [
            r'\bсогласование\b', r'\bсогласования\b'
        ],
        'otvet': [
            r'\bответ\b', r'\bответы\b', r'\bписьмо\b'
        ],
        'vhodyashie': [
            r'\bвходящие\b', r'\bвходящ\b'
        ],
        'iskhodyashie': [
            r'\bисходящие\b', r'\bисходящ\b'
        ],
        'zayavka': [
            r'\bзаявка\b', r'\bзаявки\b', r'\bзаявление\b'
        ],
        'ppr': [
            r'\bппр\b', r'\bпроект производства работ\b'
        ],
        'vdg': [
            r'\bвдг\b', r'\bвертикальная планировка\b'
        ],
        'vsss': [
            r'\bвсс\b', r'\bвертикальные сооружения связи\b'
        ],
        'btss': [
            r'\bвтсс\b', r'\bвременные технические сооружения\b'
        ],
        'ar': [
            r'\bар\b', r'\bархитектурные решения\b'
        ],
        'es': [
            r'\bэс\b', r'\bэлектроснабжение\b'
        ],
        'ts': [
            r'\bтс\b', r'\bтехнологические связи\b'
        ],
        'vs': [
            r'\bвс\b', r'\bводоснабжение\b'
        ],
        'kan': [
            r'\bкан\b', r'\bканализация\b'
        ],
        'otop': [
            r'\bотоп\b', r'\bотопление\b'
        ],
        'vent': [
            r'\bвент\b', r'\bвентиляция\b'
        ],
        'gaz': [
            r'\bгаз\b', r'\bгазоснабжение\b'
        ],
        'sot': [
            r'\bсот\b', r'\bсистема охранной телевидения\b'
        ],
        'soue': [
            r'\bсоуэ\b', r'\bсистема оповещения\b'
        ],
        'askd': [
            r'\bаскд\b', r'\bавтоматизированная система контроля доступа\b'
        ],
        'scs': [
            r'\bскс\b', r'\bструктурированная кабельная система\b'
        ],
        'lvs': [
            r'\bлвс\b', r'\bлокальная вычислительная сеть\b'
        ],
        'geo': [
            r'\bгео\b', r'\bгеодезия\b', r'\bгеоподоснова\b', r'\bгпзу\b'
        ],
        'izyskaniya': [
            r'\bизыскание\b', r'\bизыскания\b'
        ],
        'material': [
            r'\bматериал\b', r'\bматериалы\b'
        ],
        'oborudovanie': [
            r'\bоборудование\b'
        ],
        'montazh': [
            r'\bмонтаж\b'
        ],
        'demontazh': [
            r'\bдемонтаж\b'
        ],
        'rekonstrukciya': [
            r'\bреконструкция\b'
        ],
        'remont': [
            r'\bремонт\b'
        ],
        'stroitelstvo': [
            r'\bстроительство\b'
        ],
        'sp': [
            r'\bсп\b', r'\bспецификация\b'
        ],
        'shema': [
            r'\bсхема\b', r'\bсхемы\b'
        ],
        'plan': [
            r'\bплан\b', r'\bпланы\b'
        ],
        'chertezh': [
            r'\bчертеж\b', r'\bчертежи\b'
        ],
        'risunok': [
            r'\bрисунок\b', r'\bрисунки\b'
        ],
        'otchet': [
            r'\bотчет\b', r'\bотчеты\b'
        ],
        'protokol': [
            r'\bпротокол\b', r'\bпротоколы\b'
        ],
        'reshenie': [
            r'\bрешение\b', r'\bрешения\b'
        ],
        'prikaz': [
            r'\bприказ\b', r'\bприказы\b'
        ],
        'shablon': [
            r'\bшаблон\b', r'\bшаблоны\b'
        ],
        'instrukciya': [
            r'\bинструкция\b', r'\bинструкции\b'
        ],
        'polozhenie': [
            r'\bположение\b', r'\bположения\b'
        ],
        'pravila': [
            r'\bправила\b', r'\bправил\b'
        ],
        'normi': [
            r'\bнормы\b', r'\bнорм\b'
        ],
        'standart': [
            r'\bстандарт\b', r'\bстандарты\b'
        ],
        'gost': [
            r'\bгост\b', r'\bгост\b'
        ],
        'snip': [
            r'\bснип\b', r'\bснип\b'
        ],
        'metro': [
            r'\bметро\b'
        ],
        'mossvet': [
            r'\bмоссвет\b'
        ],
        'mgtc': [
            r'\bмгтс\b'
        ],
        'rostelecom': [
            r'\bростелеком\b'
        ],
        'vimpelkom': [
            r'\bвымпелком\b', r'\bбилайн\b'
        ],
        'komkor': [
            r'\bкомкор\b'
        ],
        'mptc': [
            r'\bмптц\b'
        ],
        'moslift': [
            r'\bмослифт\b'
        ],
        'oek': [
            r'\bоэк\b'
        ],
        'tsodd': [
            r'\bцодд\b'
        ],
        'rosseti': [
            r'\броссети\b'
        ],
        'mosgaz': [
            r'\bмосгаз\b'
        ],
        'sistema112': [
            r'\bсистема\s*112\b', r'\b112\b'
        ],
        'arhiv': [
            r'\bархив\b'
        ],
        'kabel': [
            r'\bкабель\b', r'\bкабельная\b'
        ],
        'trassa': [
            r'\bтрасса\b', r'\bтрасс\b'
        ],
        'kolodec': [
            r'\bколодец\b', r'\bколодцы\b'
        ],
        'kanalizaciya': [
            r'\bканализация\b'
        ],
        'osveshchenie': [
            r'\bосвещение\b'
        ],
        'ohrana': [
            r'\boхрана\b'
        ],
        'signalizaciya': [
            r'\bсигнализация\b'
        ],
        'kontrol': [
            r'\bконтроль\b'
        ],
        'dostup': [
            r'\bдоступ\b'
        ],
        'bezopasnost': [
            r'\bбезопасность\b'
        ],
        'pozharnaya': [
            r'\bпожарная\b'
        ],
        'evakuaciya': [
            r'\bэвакуация\b'
        ],
        'tehnicheski': [
            r'\bтехнический\b'
        ],
        'ekspertiza': [
            r'\bэкспертиза\b'
        ],
        'zaklyuchenie': [
            r'\bзаключение\b'
        ],
        'raschet': [
            r'\bрасчет\b'
        ],
        'geodeziya': [
            r'\bгеодезия\b'
        ],
        'inzhenerni': [
            r'\bинженерный\b'
        ],
        'sanitarni': [
            r'\bсанитарный\b'
        ],
        'protivopozharni': [
            r'\bпротивопожарный\b'
        ],
        'energetik': [
            r'\bэнергетик\b'
        ],
        'svyaz': [
            r'\bсвязь\b'
        ],
        'telefon': [
            r'\bтелефон\b'
        ],
        'internet': [
            r'\bинтернет\b'
        ],
        'telekommunikaciya': [
            r'\bтелекоммуникация\b'
        ],
        'ekonomicheski': [
            r'\bэкономический\b'
        ],
        'finansovi': [
            r'\bфинансовый\b'
        ],
        'zakonodatelni': [
            r'\bзаконодательный\b'
        ],
        'normativni': [
            r'\bнормативный\b'
        ],
        'geologicheski': [
            r'\bгеологический\b'
        ],
        'ecologicheski': [
            r'\bэкологический\b'
        ],
        'stroitelni': [
            r'\bстроительный\b'
        ],
        'montazhni': [
            r'\bмонтажный\b'
        ],
        'ekspluataciya': [
            r'\bэксплуатация\b'
        ],
        'proektirovanie': [
            r'\bпроектирование\b'
        ],
        'stroitelstvo': [
            r'\bстроительство\b'
        ],
        'rekonstrukciya': [
            r'\bреконструкция\b'
        ],
        'kapitalni': [
            r'\bкапитальный\b'
        ],
        'remontni': [
            r'\bремонтный\b'
        ],
        'tekushchi': [
            r'\bтекущий\b'
        ],
        'aktualni': [
            r'\bактуальный\b'
        ],
        'proektni': [
            r'\bпроектный\b'
        ],
        'organizacionni': [
            r'\bорганизационный\b'
        ],
        'tehnologicheski': [
            r'\bтехнологический\b'
        ],
        'puskonaladochni': [
            r'\bпусконаладочный\b'
        ],
        'gipro': [
            r'\bгипро\b'
        ],
        'mosproject': [
            r'\bмоспроект\b'
        ],
        'stroiproekt': [
            r'\bстройпроект\b'
        ],
        'inzhproekt': [
            r'\bинжпроект\b'
        ],
        'giprotrans': [
            r'\bгипротранс\b'
        ],
        'giprovod': [
            r'\bгипровод\b'
        ],
        'giprogaz': [
            r'\bгипрогаз\b'
        ],
        'giproenergo': [
            r'\bгипроэнерго\b'
        ],
        'giprosvyaz': [
            r'\bгипросвязь\b'
        ],
        'giprogor': [
            r'\bгипрогор\b'
        ],
        'giprodor': [
            r'\bгипродор\b'
        ],
        'gipromost': [
            r'\bгипромост\b'
        ],
        'giprosnab': [
            r'\bгипроснаб\b'
        ],
        'giprospec': [
            r'\bгипроспец\b'
        ],
        'giproteh': [
            r'\bгипротех\b'
        ],
        'gipromezh': [
            r'\bгипромеж\b'
        ],
        'stroymechanizaciya': [
            r'\bстроймеханизация\b'
        ],
        'stroidetal': [
            r'\bстройдеталь\b'
        ],
        'stroimaterial': [
            r'\bстройматериал\b'
        ],
        'stroikomplekt': [
            r'\bстройкомплект\b'
        ],
        'stroiservis': [
            r'\bстройсервис\b'
        ],
        'moskva': [
            r'\bмосква\b', r'\bмск\b'
        ],
        'ul': [
            r'\bул\.\s*\w+', r'\bулица\b'
        ],
        'bulvar': [
            r'\bбульвар\b'
        ],
        'prospekt': [
            r'\bпроспект\b'
        ],
        'shosse': [
            r'\bшоссе\b'
        ],
        'pereulok': [
            r'\bпереулок\b'
        ],
        'proezd': [
            r'\bпроезд\b'
        ],
        'ploshad': [
            r'\bплощадь\b'
        ],
        'mikrorayon': [
            r'\bмикрорайон\b'
        ],
        'rayon': [
            r'\bрайон\b'
        ],
        'okrug': [
            r'\bокруг\b'
        ],
        'poselok': [
            r'\bпоселок\b'
        ],
        'derevnya': [
            r'\bдеревня\b'
        ],
        'snt': [
            r'\bснт\b'
        ],
        'kvartal': [
            r'\bквартал\b'
        ],
        'masshtab': [
            r'\bмасштаб\b'
        ],
        'shifr': [
            r'\bшифр\b'
        ],
        'nomer': [
            r'\bномер\b', r'\b№\s*\d+'
        ],
        'data': [
            r'\bдата\b'
        ],
        'period': [
            r'\bпериод\b'
        ],
        'etap': [
            r'\bэтап\b'
        ],
        'chast': [
            r'\bчасть\b'
        ],
        'razdel': [
            r'\bраздел\b'
        ],
        'punkt': [
            r'\bпункт\b'
        ],
        'prilozhenie': [
            r'\bприложение\b'
        ],
        'addendum': [
            r'\bдополнение\b'
        ],
        'popravka': [
            r'\bпоправка\b'
        ],
        'izmenenie': [
            r'\bизменение\b', r'\bизм\.\s*\d+'
        ],
        'korrekt': [
            r'\bкоррект\b', r'\bкорректировка\b'
        ],
        'redakciya': [
            r'\bредакция\b', r'\bред\b'
        ],
        'novi': [
            r'\bновый\b', r'\bнов\b'
        ],
        'stari': [
            r'\bстарый\b', r'\bстар\b'
        ],
        'aktualni': [
            r'\bактуальный\b'
        ],
        'rabochi': [
            r'\bрабочий\b'
        ],
        'tehnich': [
            r'\bтехнический\b'
        ],
        'giprostroi': [
            r'\bгипрострой\b'
        ],
        'lenprom': [
            r'\bлентроп\b'
        ],
        'mosinzhproekt': [
            r'\bмосинжпроект\b'
        ],
        'gipro': [
            r'\bгипро\b'
        ],
        'mosproject': [
            r'\bмоспроект\b'
        ],
        'stroiproekt': [
            r'\bстройпроект\b'
        ],
        'inzhproekt': [
            r'\bинжпроект\b'
        ],
        'giprotrans': [
            r'\bгипротранс\b'
        ],
        'giprovod': [
            r'\bгипровод\b'
        ],
        'giprogaz': [
            r'\bгипрогаз\b'
        ],
        'giproenergo': [
            r'\bгипроэнерго\b'
        ],
        'giprosvyaz': [
            r'\bгипросвязь\b'
        ],
        'giprogor': [
            r'\bгипрогор\b'
        ],
        'giprodor': [
            r'\bгипродор\b'
        ],
        'gipromost': [
            r'\bгипромост\b'
        ],
        'giprosnab': [
            r'\bгипроснаб\b'
        ],
        'giprospec': [
            r'\bгипроспец\b'
        ],
        'giproteh': [
            r'\bгипротех\b'
        ],
        'gipromezh': [
            r'\bгипромеж\b'
        ],
        'giprostroymash': [
            r'\bгипростроймаш\b'
        ],
        'stroymechanizaciya': [
            r'\bстроймеханизация\b'
        ],
        'stroidetal': [
            r'\bстройдеталь\b'
        ],
        'stroimaterial': [
            r'\bстройматериал\b'
        ],
        'stroikomplekt': [
            r'\bстройкомплект\b'
        ],
        'stroiservis': [
            r'\bстройсервис\b'
        ],
        'gupro': [
            r'\bгупро\b'
        ],
        'mup': [
            r'\bмуп\b'
        ],
        'gu': [
            r'\bгу\b'
        ],
        'mk': [
            r'\bмк\b'
        ],
        'msp': [
            r'\bмсп\b'
        ],
        'mfc': [
            r'\bмфц\b'
        ],
        'mnp': [
            r'\bмнп\b'
        ],
        'sz': [
            r'\bсз\b'
        ],
        'uz': [
            r'\bуз\b'
        ],
        'uo': [
            r'\буо\b'
        ],
        'uoo': [
            r'\буоо\b'
        ],
        'zao': [
            r'\bзао\b'
        ],
        'ooo': [
            r'\bооо\b'
        ],
        'ip': [
            r'\bип\b'
        ],
        'ao': [
            r'\bао\b'
        ],
        'oao': [
            r'\bоао\b'
        ],
        'pao': [
            r'\bпао\b'
        ],
        'gup': [
            r'\bгуп\b'
        ],
        'gbu': [
            r'\bгбу\b'
        ],
        'fce': [
            r'\bфцэ\b'
        ],
        'mbu': [
            r'\bмбу\b'
        ],
        'dsk': [
            r'\bдск\b'
        ],
        'dk': [
            r'\bдк\b'
        ],
        'dku': [
            r'\bдку\b'
        ],
        'ku': [
            r'\bку\b'
        ],
        'ktu': [
            r'\bкту\b'
        ],
        'dnp': [
            r'\bднп\b'
        ],
        'nd': [
            r'\bнд\b'
        ],
        'tdd': [
            r'\bтдд\b'
        ],
        'td': [
            r'\bтд\b'
        ],
        'tdr': [
            r'\bтдр\b'
        ],
        'tkr': [
            r'\bткр\b'
        ],
        'os': [
            r'\bос\b'
        ],
        'oos': [
            r'\боос\b'
        ],
        'pd': [
            r'\bпд\b'
        ],
        'td': [
            r'\bтд\b'
        ],
        'tm': [
            r'\bтм\b'
        ],
        'gm': [
            r'\bгм\b'
        ],
        'msu': [
            r'\bмсу\b'
        ],
        'mgsu': [
            r'\bмгсу\b'
        ],
        'mis': [
            r'\bмис\b'
        ],
        'mgsn': [
            r'\bмгсн\b'
        ],
        'mgsoe': [
            r'\bмгсоэ\b'
        ],
        'sk': [
            r'\bск\b'
        ],
        'ls': [
            r'\bлс\b'
        ],
        'kp': [
            r'\bкп\b'
        ],
        'kst': [
            r'\bкст\b', r'\bкгс\b'
        ],
        'ks': [
            r'\bкс\b'
        ],
        'k': [
            r'\bкорпус\b'
        ],
        'v': [
            r'\bвариант\b'
        ],
        'iz': [
            r'\bизменение\b'
        ],
        'nov': [
            r'\bновый\b'
        ],
        'star': [
            r'\bстарый\b'
        ],
        'scan': [
            r'\bскан\b', r'\bсканировка\b'
        ],
        'kop': [
            r'\bкопия\b', r'\bкоп\b'
        ],
        'orig': [
            r'\bоригинал\b', r'\bориг\b'
        ],
        'svod': [
            r'\bсводный\b', r'\bсвод\b'
        ],
        'uch': [
            r'\bучасток\b'
        ],
        'uchet': [
            r'\bучет\b'
        ],
        'sved': [
            r'\бсведения\b'
        ],
        'perv': [
            r'\bпервичный\b'
        ],
        'vtor': [
            r'\bвторичный\b'
        ],
        'tret': [
            r'\bтретичный\b'
        ],
        'chet': [
            r'\bчетвертый\b'
        ],
        'pyat': [
            r'\bпятый\b'
        ],
        'shest': [
            r'\bшестой\b'
        ],
        'sem': [
            r'\bседьмой\b'
        ],
        'vos': [
            r'\bвосьмой\b'
        ],
        'devyat': [
            r'\bдевятый\b'
        ],
        'desyat': [
            r'\bдесятый\b'
        ],
        'odin': [
            r'\bпервый\b'
        ],
        'dva': [
            r'\bвторой\b'
        ],
        'tri': [
            r'\bтретий\b'
        ],
        'chetire': [
            r'\bчетвертый\b'
        ],
        'pyat': [
            r'\bпятый\b'
        ],
        'shest': [
            r'\bшестой\b'
        ],
        'sem': [
            r'\bседьмой\b'
        ],
        'vosem': [
            r'\bвосьмой\b'
        ],
        'devyat': [
            r'\bдевятый\b'
        ],
        'desyat': [
            r'\bдесятый\b'
        ],
        'sto': [
            r'\bсотня\b'
        ],
        'dvisti': [
            r'\bдвухсот\b'
        ],
        'trista': [
            r'\bтрехсот\b'
        ],
        'chetiresta': [
            r'\bчетыреста\b'
        ],
        'pyatsot': [
            r'\bпятисот\b'
        ],
        'shestsot': [
            r'\bшестисот\b'
        ],
        'semsot': [
            r'\bсемисот\b'
        ],
        'vosemsot': [
            r'\bвосемисот\b'
        ],
        'devyatsot': [
            r'\bдевятьсот\b'
        ],
        'tisyacha': [
            r'\bтысяча\b'
        ],
        'god': [
            r'\bгод\b'
        ],
        'mesyac': [
            r'\bмесяц\b'
        ],
        'den': [
            r'\bдень\b'
        ],
        'chas': [
            r'\bчас\b'
        ],
        'minuta': [
            r'\bминута\b'
        ],
        'sekunda': [
            r'\bсекунда\b'
        ],
        'janvar': [
            r'\bянварь\b'
        ],
        'fevral': [
            r'\bфевраль\b'
        ],
        'mart': [
            r'\bмарт\b'
        ],
        'aprel': [
            r'\bапрель\b'
        ],
        'may': [
            r'\bмай\b'
        ],
        'iyun': [
            r'\bиюнь\b'
        ],
        'iyul': [
            r'\bиюль\b'
        ],
        'avgust': [
            r'\bавгуст\b'
        ],
        'sentyabr': [
            r'\bсентябрь\b'
        ],
        'oktyabr': [
            r'\bоктябрь\b'
        ],
        'noyabr': [
            r'\bноябрь\b'
        ],
        'dekabr': [
            r'\bдекабрь\b'
        ],
        'tu_oper': [
            r'\bту\s*оператор\b'
        ],
        'ktu': [
            r'\bкту\b'
        ],
        'kommunikaciya': [
            r'\bкоммуникации\b'
        ],
        'signalizaciya': [
            r'\bсигнализация\b'
        ],
        'kontrol': [
            r'\bконтроль\b'
        ],
        'dostup': [
            r'\bдоступ\b'
        ],
        'bezopasnost': [
            r'\bбезопасность\b'
        ],
        'pozharnaya': [
            r'\bпожарная\b'
        ],
        'evakuaciya': [
            r'\bэвакуация\b'
        ],
        'dymoudalenie': [
            r'\bдымоудаление\b'
        ],
        'vodosnabzhenie': [
            r'\bводоснабжение\b'
        ],
        'kanalizaciya': [
            r'\bканализация\b'
        ],
        'otoplenie': [
            r'\bотопление\b'
        ],
        'ventilyaciya': [
            r'\bвентиляция\b'
        ],
        'gazosnabzhenie': [
            r'\bгазоснабжение\b'
        ],
        'elektrosnabzhenie': [
            r'\bэлектроснабжение\b'
        ],
        'stroitelstvo': [
            r'\bстроительство\b'
        ],
        'montazh': [
            r'\bмонтаж\b'
        ],
        'rekonstrukciya': [
            r'\bреконструкция\b'
        ],
        'kapitalni': [
            r'\bкапитальный\b'
        ],
        'remontni': [
            r'\bремонтный\b'
        ],
        'tekushchi': [
            r'\bтекущий\b'
        ],
        'proektirovanie': [
            r'\bпроектирование\b'
        ],
        'stroitelni': [
            r'\bстроительный\b'
        ],
        'montazhni': [
            r'\bмонтажный\b'
        ],
        'puskonaladochni': [
            r'\bпусконаладочный\b'
        ],
        'ekspluataciya': [
            r'\bэксплуатация\b'
        ],
        'tehnicheski': [
            r'\bтехнический\b'
        ],
        'tehnologicheski': [
            r'\bтехнологический\b'
        ],
        'organizacionni': [
            r'\bорганизационный\b'
        ],
        'ekonomicheski': [
            r'\bэкономический\b'
        ],
        'finansovi': [
            r'\bфинансовый\b'
        ],
        'dogovorni': [
            r'\bдоговорной\b'
        ],
        'zakonodatelni': [
            r'\bзаконодательный\b'
        ],
        'normativni': [
            r'\bнормативный\b'
        ],
        'tehnicheski': [
            r'\bтехнический\b'
        ],
        'raschetni': [
            r'\bрасчетный\b'
        ],
        'geologicheski': [
            r'\bгеологический\b'
        ],
        'geodezicheski': [
            r'\bгеодезический\b'
        ],
        'genezicheski': [
            r'\bгенизический\b'
        ],
        'gidrotehnicheski': [
            r'\bгидротехнический\b'
        ],
        'metallurgicheski': [
            r'\bметаллургический\b'
        ],
        'himicheski': [
            r'\bхимический\b'
        ],
        'biologicheski': [
            r'\bбиологический\b'
        ],
        'ecologicheski': [
            r'\bэкологический\b'
        ],
        # NB: duplicate 'invoice'/'estimate'/'project'/'passport' definitions
        # removed — they overwrote the earlier blocks (incl. Russian patterns).
        'contract': [
            r'\bcontract\b'
        ],
        # --- Frequent real-world names missing from earlier patterns ---
        'titul': [
            r'\bтитул\b', r'\bтитульный\b', r'\bтитульный\s*лист\b'
        ],
        'oblozhka': [
            r'\bобложка\b', r'\bтитульный\s*лист\b'
        ],
        'soderzhanie': [
            r'\bсодержание\b'
        ],
        'vedomost': [
            r'\bведомость\b', r'\bведомости\b', r'\bведомостей\b'
        ],
        'profil': [
            r'\bпрофиль\b', r'\bпродольный\b', r'\bпоперечный\b',
            r'\bпродольн\b', r'\bпоперечн\b'
        ],
        'vynos': [
            r'\bвынос\b', r'\bвыноска\b', r'\bвыноски\b'
        ],
        'sborka': [
            r'\bсборочный\b', r'\bсборная\b', r'\bсборке\b',
            r'\bсборочный\s*чертеж\b'
        ],
        'uzel': [
            r'\bузел\b', r'\bузлы\b', r'\bдеталь\b', r'\bдетали\b'
        ],
        'sertifikat': [
            r'\bсертификат\b', r'\bсертификаты\b'
        ],
        'vypiska': [
            r'\bвыписка\b', r'\bвыписки\b'
        ],
        'list': [
            r'\bлист\b', r'\bлисты\b', r'\bлист\b\s*[0-9]'
        ],
        'pasport_svyazi': [
            r'\bпаспорт\s*линии\b', r'\bпаспорт\s*кабеля\b',
            r'\bпаспорт\s*трассы\b', r'\bпаспорт\s*объекта\b'
        ],
        'kpmptc': [
            r'\bкпмптц\b', r'\bкп\s*мптц\b'
        ],
        'aosr': [
            r'\bаоср\b'
        ],
        'vspomogatelni': [
            r'\bвспомогательный\b', r'\bвспомогательные\b'
        ],
        'opis': [
            r'\bопись\b', r'\bописи\b'
        ],
        'zayavlenie_telco': [
            r'\bзаявление\s*оператору\b', r'\bзаявка\s*оператору\b'
        ],
        'narisovanie': [
            r'\bнарисовани\b', r'\bзарисовани\b'
        ],
        'zhurnal': [
            r'\bжурнал\b', r'\bжурнала\b', r'\bжурналы\b'
        ],
        'akt_sverki': [
            r'\bакт\s*сверки\b', r'\bсверка\b'
        ],
        'doverennost': [
            r'\bдоверенность\b', r'\bдоверенности\b'
        ],
        'kommerscheskoe': [
            r'\bкоммерческое\b', r'\bкоммерческий\b', r'\bкп\b(?!\w)'
        ],
        'polozhenie_grunt': [
            r'\bположение\s*о\s*землях\b', r'\bкадастровый\b'
        ],
        'soglashenie': [
            r'\bсоглашение\b', r'\bдополнительное\s*соглашение\b',
            r'\bдоп\s*соглашение\b', r'\bдоп\s*соглаш\b'
        ],
        'kombinirovannoe': [
            r'\bкомбинированный\b'
        ],
        'sbivochniy': [
            r'\bсбивочный\b', r'\bсбивка\b'
        ],
        'raschetniy_list': [
            r'\bрасчетный\s*лист\b', r'\bрасчетный\b'
        ],
        'perechen': [
            r'\bперечень\b', r'\bсписок\b'
        ],
        'tabl': [
            r'\bтаблица\b', r'\bтаблицы\b'
        ],
        'zametki': [
            r'\bзаметки\b', r'\bнаброски\b'
        ],
        'chernovik': [
            r'\bчерновик\b', r'\bчерновой\b'
        ],
        'razrabotka': [
            r'\bразработка\b', r'\bразработки\b', r'\bразработан\b'
        ],
        'grunt': [
            r'\bгрунт\b', r'\bгрунта\b', r'\bгрунтов\b',
            r'\bинженерно\s*геологическ\b', r'\bвеерн\b'
        ],
        'truba': [
            r'\bтруба\b', r'\bтрубы\b', r'\bтрубопровод\b',
            r'\bпайп\b', r'\bpipe\b'
        ],
        'obratnaya_zasypka': [
            r'\bобратная\b', r'\bзасыпка\b', r'\bзасыпки\b'
        ],
        'reestr': [
            r'\bреестр\b', r'\bреестра\b', r'\bреестры\b'
        ],
        'poruchenie': [
            r'\bпоручение\b', r'\bпоручения\b'
        ],
        'platezh': [
            r'\bплатежное\b', r'\bплатеж\b', r'\bплатежи\b',
            r'\bоплата\b', r'\bсчет\s*фактура\b', r'\bсчет-фактура\b'
        ],
        'dannye': [
            r'\bданные\b', r'\bданных\b', r'\bисходные\b'
        ],
        'karta': [
            r'\bкарта\b', r'\bкарты\b', r'\bкадастр\b'
        ],
        'dopusk': [
            r'\bдопуск\b', r'\bдопуска\b', r'\bдопущен\b'
        ],
        'mufta': [
            r'\bмуфта\b', r'\bмуфты\b', r'\bсварк\b'
        ],
        'kanal': [
            r'\bканализ\b', r'\bканализация\b', r'\bливнев\b',
            r'\bдождев\b'
        ],
        'mksi': [
            r'\bмкси\b', r'\bкппмптц\b', r'\bмптц\b'
        ],
        'igdi': [
            r'\bигди\b'
        ],
        'corp': [
            r'\bкорп\b', r'\bкорпус\b'
        ],
        'tehnologicheskaya': [
            r'\bтехнологическая\b', r'\bтехнологии\b'
        ],
        'polosatik': [
            r'\bполосатик\b'
        ],
        'summa': [
            r'\bсумму\b', r'\bсумма\b', r'\bсумм\b', r'\bитого\b'
        ],
        'otgruzka': [
            r'\bотгр\b', r'\bотгрузк\b', r'\bотгружен\b'
        ],
        'zakl': [
            r'\bзакл\b', r'\bзаключение\b', r'\bзакрытие\b'
        ],
        'sootv': [
            r'\bсоотв\b', r'\bсоответствии\b'
        ],
    }
    
    # Word-boundary shorthand: separators like _ - . ( ) should behave like spaces
    _SEPARATORS_RE = re.compile(r'[_\-\.\(\)\[\]#,+]+')
    
    # Compiled pattern cache: (doc_type, pattern) -> compiled regex
    _COMPILED: Dict[Any, re.Pattern] = {}
    
    # More specific types must be checked before generic ones
    # (e.g. 'Титул_проекта' is a title page, not a project;
    #  'Акт_сверки' is a reconciliation act, not just an act)
    _PRIORITY_TYPES = (
        'titul', 'oblozhka', 'soderzhanie', 'vedomost', 'sborka',
        'akt_sverki', 'pasport_svyazi', 'chernovik', 'zakl',
        'platezh', 'soglashenie', 'aktualni',
    )
    
    @classmethod
    def _ordered_items(cls):
        """Yield (doc_type, patterns) with priority types first."""
        seen = set()
        for key in cls._PRIORITY_TYPES:
            if key in cls.PATTERNS:
                seen.add(key)
                yield key, cls.PATTERNS[key]
        for key, patterns in cls.PATTERNS.items():
            if key not in seen:
                yield key, patterns
    
    @classmethod
    def _compiled_patterns(cls):
        """Yield (doc_type, compiled_regex) pairs, compiling once per pattern."""
        for doc_type, patterns in cls._ordered_items():
            for pattern in patterns:
                key = (doc_type, pattern)
                compiled = cls._COMPILED.get(key)
                if compiled is None:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    cls._COMPILED[key] = compiled
                yield doc_type, compiled
    
    @classmethod
    def _normalize(cls, filename: str) -> str:
        """Lowercase and turn file-name separators into spaces so that \\b
        word boundaries work for names like 'паспорт_трассы' or 'РД-01'."""
        return cls._SEPARATORS_RE.sub(' ', filename.lower())
    
    def classify(self, filename: str) -> str:
        """Classify document using regex patterns"""
        normalized = self._normalize(filename)
        
        # Check each pattern for each document type (compiled once, cached)
        for doc_type, compiled in self._compiled_patterns():
            if compiled.search(normalized):
                return doc_type
        
        # Extension fallbacks for CAD files and their service files
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext in self.CAD_SERVICE_EXTS:
            return 'cad_service'
        if ext in self.CAD_EXTS:
            return 'cad_drawing'
        if ext in {'jpg', 'jpeg', 'png', 'tiff', 'bmp', 'gif'}:
            return 'image'
        if ext in {'zip', 'rar', '7z'}:
            return 'archive'
        
        return 'unknown'
    
    def classify_batch(self, filenames: List[str]) -> Dict[str, int]:
        """Classify a batch of filenames and return statistics"""
        classifications = {}
        
        for filename in filenames:
            doc_type = self.classify(filename)
            classifications[doc_type] = classifications.get(doc_type, 0) + 1
        
        return classifications