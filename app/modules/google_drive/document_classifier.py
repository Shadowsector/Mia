"""Improved document classifier with focused patterns"""

import re
from typing import Dict, List

class ImprovedDocumentClassifier:
    """Classifier with focused patterns for construction documents"""
    
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
            r'\bпаспорт\s*[а-я]\b'
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
        'invoice': [
            r'\binvoice\b'
        ],
        'estimate': [
            r'\bestimate\b'
        ],
        'contract': [
            r'\bcontract\b'
        ],
        'project': [
            r'\bproject\b'
        ],
        'passport': [
            r'\bpassport\b'
        ]
    }
    
    def classify(self, filename: str) -> str:
        """Classify document using regex patterns"""
        filename_lower = filename.lower()
        
        # Check each pattern for each document type
        for doc_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return doc_type
        
        return 'unknown'
    
    def classify_batch(self, filenames: List[str]) -> Dict[str, int]:
        """Classify a batch of filenames and return statistics"""
        classifications = {}
        
        for filename in filenames:
            doc_type = self.classify(filename)
            classifications[doc_type] = classifications.get(doc_type, 0) + 1
        
        return classifications