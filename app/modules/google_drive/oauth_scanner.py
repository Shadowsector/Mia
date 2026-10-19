"""Google Drive Scanner using OAuth 2.0 authentication"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

logger = logging.getLogger(__name__)


class OAuthDriveScanner:
    """Scanner for Google Drive using OAuth 2.0 authentication"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    TOKEN_FILE = 'config/google_drive_token.json'
    
    # Additional scope for Shared Drives
    SUPPORTS_ALL_DRIVES = True
    
    FILE_TYPE_CATEGORIES = {
        'office_documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'],
        'cad_drawings': ['.dwg', '.dxf', '.dwf'],
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'],
        'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'text': ['.txt', '.csv', '.json', '.xml'],
        'other': []
    }
    
    DOCUMENT_TYPE_KEYWORDS = {
        'rd': ['рд', 'рабочая документация', 'рабочий документ', 'рабочая', 'раб_док'],
        'sps': ['спс', 'строительные проектные решения', 'строит проект решен', 'проектное решение'],
        'pzu': ['пзу', 'проектные решения узлов', 'проект решен узл', 'узл'],
        'tu': ['ту', 'технические условия', 'тех условие', 'тех_усл'],
        'nss': ['нсс', 'наружные сооружения связи', 'нар сооруж связ', 'наружн связь'],
        'id': ['ид', 'исходные данные', 'исходн данн', 'исх_данн', 'техз', 'техническое задание'],
        'gp': ['гп', 'генеральный план', 'ген план', 'генплан'],
        'ops': ['опс', 'организация строительной площадки', 'организац строит площадк', 'стройгенплан'],
        'pos': ['пос', 'проект организации строительства', 'проект организ строит'],
        'pir': ['пир', 'проектно-изыскательские работы', 'проект изыскательск рабоч', 'изыскания'],
        'act': ['акт', 'акты', 'акт_', 'акт-'],
        'spravka': ['справка', 'справки', 'справ_', 'спр_'],
        'passport': ['паспорт', 'пасп', 'паспорта', 'паспорт_'],
        'smeta': ['смета', 'сметы', 'смет_', 'см_'],
        'dogovor': ['договор', 'contract', 'соглашение', 'дог_', 'дог-', 'согл_', 'согл-'],
        'schet': ['счет', 'счета', 'счет_', 'сч_', 'накладная', 'накл', 'упд'],
        'invoice': ['invoice', 'invoice_'],
        'estimate': ['estimate', 'estimate_'],
        'project': ['проект', 'project', 'проект_', 'проект-'],
        'zamechaniya': ['замечание', 'замечания', 'замеч_', 'зам_', 'отзыв'],
        'soglasovanie': ['согласование', 'согласования', 'согл_', 'соглас_', 'согласован'],
        'otvet': ['ответ', 'ответы', 'ответ_', 'отв_', 'письмо', 'письма', 'письм_', 'пис_'],
        'vhodyashie': ['входящие', 'входящ', 'вход_', 'вх_'],
        'iskhodyashie': ['исходящие', 'исходящ', 'исход_', 'исх_'],
        'zayavka': ['заявка', 'заявки', 'заяв_', 'заяв-', 'заявление'],
        'opros': ['опрос', 'опросы', 'опрос_'],
        'kst': ['кст', 'кгс', 'кассовый чек', 'касс'],
        'ppr': ['ппр', 'проект производства работ', 'производство работ'],
        'vdg': ['вдг', 'вертикальная планировка', 'вертикальн план'],
        'vsss': ['всс', 'вертикальные сооружения связи', 'вертикальн сооруж связ'],
        'btss': ['втсс', 'временные технические сооружения', 'врем техн сооруж'],
        'vtp': ['втп', 'вертикальная транспортная развязка', 'вертикальн трансп развязк'],
        'ar': ['ар', 'архитектурные решения', 'архитектурн решен'],
        'es': ['эс', 'электроснабжение', 'электроснабжен', 'электр'],
        'ts': ['тс', 'технологические связи', 'технологич связ'],
        'vs': ['вс', 'водоснабжение', 'водоснабжен'],
        'kan': ['кан', 'канализация', 'канализац'],
        'otop': ['отоп', 'отопление', 'отоплен'],
        'vent': ['вент', 'вентиляция', 'вентиляц'],
        'gaz': ['газ', 'газоснабжение', 'газоснабжен'],
        'sot': ['сот', 'система охранной телевидения', 'охр телевиз'],
        'soue': ['соуэ', 'система оповещения', 'оповещен'],
        'askd': ['аскд', 'автоматизированная система контроля доступа', 'автомат контр доступ'],
        'scs': ['скс', 'структурированная кабельная система', 'структур кабельн систем'],
        'lvs': ['лвс', 'локальная вычислительная сеть', 'локальн вычислит сет'],
        'rd_svoe': ['рд св', 'сводный план', 'сводн план'],
        'geo': ['гео', 'геодезия', 'геодезическ', 'геоподоснова', 'геоп', 'гпзу'],
        'izyskaniya': ['изыскание', 'изыскания', 'изыскан', 'изыск_'],
        'transport': ['транспорт', 'трасса', 'трасс', 'тр_'],
        'kommunikaciya': ['коммуникация', 'коммуникации', 'коммуник', 'комм_'],
        'material': ['материал', 'материалы', 'матер_'],
        'oborudovanie': ['оборудование', 'оборудован', 'оборуд_'],
        'montazh': ['монтаж', 'монтаж_', 'монт_'],
        'demontazh': ['демонтаж', 'демонтаж_', 'демонт_'],
        'rekonstrukciya': ['реконструкция', 'реконструкц', 'реконстр_'],
        'remont': ['ремонт', 'ремонт_', 'рем_'],
        'stroitelstvo': ['строительство', 'строител', 'строит_'],
        'sp': ['сп', 'спецификация', 'спецификац', 'спец_'],
        'tu_oper': ['ту оператор', 'ту оператора', 'ту_опер'],
        'ktu': ['кту', 'корректировка технических условий', 'коррект техн услов'],
        'reduct': ['ред', 'редакция', 'редакц', 'ред_', 'ред-'],
        'korrekt': ['коррект', 'корректировка', 'коррект_', 'коррект-'],
        'lib': ['lib', 'библиотека', 'библиотек', 'библиот_'],
        'xref': ['xref', 'внешние ссылки', 'внешн ссылк'],
        'plotcfg': ['plotcfg', 'конфигурация чертежа', 'конфиг чертеж'],
        'texture': ['texture', 'текстура', 'текстур'],
        'fonts': ['fonts', 'шрифты', 'шрифт'],
        'model': ['model', 'модель', 'модел'],
        'block': ['block', 'блок', 'блок_'],
        'layer': ['layer', 'слой', 'сло'],
        'shablon': ['шаблон', 'шаблон_', 'шабл_'],
        'titul': ['титул', 'титульный', 'титул_'],
        'oblozhka': ['обложка', 'обложк', 'облож_'],
        'sohran': ['сохран', 'сохранн', 'сохран_'],
        'metro': ['метро', 'метр_'],
        'mossvet': ['моссвет', 'моссвет_', 'наружн освещен'],
        'mgtc': ['мгтс', 'мгтс_', 'московск городск телефонн сет'],
        'rostelecom': ['ростелеком', 'ростелеком_', 'ртк'],
        'vimpelkom': ['вымпелком', 'вымпелком_', 'билайн'],
        'komkor': ['комкор', 'комкор_'],
        'mptc': ['мптц', 'мостелефонн центр'],
        'moslift': ['мослифт', 'мослифт_'],
        'oek': ['оэк', 'оэк_'],
        'moek': ['моэк', 'моэк_'],
        'mosgaz': ['мосгаз', 'мосгаз_'],
        'tsodd': ['цодд', 'цодд_'],
        'rosseti': ['россети', 'россет_', 'россет'],
        'rubin': ['рубин', 'рубин_'],
        'sistema112': ['система 112', 'систем112', '112'],
        'ime': ['имц', 'имц_'],
        'rsv0': ['рсв0', 'рсв0_'],
        'mvs': ['мвс', 'мвс_'],
        'mvk': ['мвк', 'мвк_'],
        'kod': ['код', 'код_', 'код-'],
        'shifr': ['шифр', 'шифр_', 'шиф-'],
        'nomer': ['номер', 'номер_', 'ном_', '№'],
        'data': ['дата', 'дата_', 'дат_'],
        'period': ['период', 'период_', 'период-'],
        'etap': ['этап', 'этап_', 'этап-'],
        'chast': ['часть', 'часть_', 'част_', 'ч-'],
        'razdel': ['раздел', 'раздел_', 'разд_', 'р-'],
        'punkt': ['пункт', 'пункт_', 'пункт-'],
        'prilozhenie': ['приложение', 'приложен', 'прилож_', 'прил_'],
        'addendum': ['дополнение', 'дополнен', 'дополн_', 'доп_'],
        'popravka': ['поправка', 'поправк', 'поправ_'],
        'izmenenie': ['изменение', 'изменен', 'измен_', 'изм_', 'изм-'],
        'arhiv': ['архив', 'архив_', 'арх_'],
        'rabochi': ['рабочий', 'рабоч_', 'раб_'],
        'tekushchi': ['текущий', 'текущ_', 'текущ-'],
        'aktualni': ['актуальный', 'актуальн', 'актуал_'],
        'stroiteln': ['строительный', 'строительн', 'строит_'],
        'proektni': ['проектный', 'проектн', 'проект_'],
        'tehnich': ['технический', 'техническ', 'технич_'],
        'ekspertiza': ['экспертиза', 'экспертиз', 'эксперт'],
        'zaklyuchenie': ['заключение', 'заключен', 'заключ_'],
        'raschet': ['расчет', 'расчет_', 'расч_'],
        'shema': ['схема', 'схемы', 'схем_', 'сх_'],
        'plan': ['план', 'планы', 'план_', 'пл_'],
        'profil': ['профиль', 'профили', 'профил_', 'проф_'],
        'razrez': ['разрез', 'разрезы', 'разрез_', 'разр_'],
        'fasad': ['фасад', 'фасады', 'фасад_', 'фас_'],
        'planirovka': ['планировка', 'планировк', 'планир_'],
        'sechenie': ['сечение', 'сечения', 'сечен_', 'сеч_'],
        'uzel': ['узел', 'узлы', 'узел_', 'уз_'],
        'sooruzhenie': ['сооружение', 'сооружен', 'сооруж_'],
        'zdanie': ['здание', 'здания', 'зда_'],
        'sooruzheniya': ['сооружения', 'сооружен_'],
        'uchastok': ['участок', 'участк', 'участ_'],
        'territoriya': ['территория', 'территор', 'террит_'],
        'zon': ['зона', 'зоны', 'зон_'],
        'kvartal': ['квартал', 'квартал_', 'кварт_'],
        'uchastok': ['участок', 'участок_'],
        'masshtab': ['масштаб', 'масштаб_'],
        'orientir': ['ориентир', 'ориентир_'],
        'geodeziya': ['геодезия', 'геодезия_'],
        'inzhener': ['инженер', 'инженер_'],
        'inzhenerni': ['инженерный', 'инженерн_'],
        'sanitarni': ['санитарный', 'санитарн_'],
        'protivopozharni': ['противопожарный', 'противопожарн_'],
        'energetik': ['энергетик', 'энергетик_'],
        'svyaz': ['связь', 'связ_'],
        'telefon': ['телефон', 'телефон_'],
        'internet': ['интернет', 'интернет_'],
        'telekommunikaciya': ['телекоммуникация', 'телекоммуникац_'],
        'kabel': ['кабель', 'кабел_'],
        'trassa': ['трасса', 'трасс_'],
        'kolodec': ['колодец', 'колодц_', 'к-'],
        'kanalizaciya': ['канализация', 'канализац_'],
        'vodoprovod': ['водопровод', 'водопров_'],
        'teploprovod': ['теплопровод', 'теплопров_'],
        'gazoprovod': ['газопровод', 'газопров_'],
        'elektroprovod': ['электропровод', 'электропров_'],
        'ventilyaciya': ['вентиляция', 'вентиляц_'],
        'kondicionirovanie': ['кондиционирование', 'кондиционир_'],
        'osveshchenie': ['освещение', 'освещен_'],
        'ohrana': ['охрана', 'охран_'],
        'signalizaciya': ['сигнализация', 'сигнализ_'],
        'kontrol': ['контроль', 'контрол_'],
        'dostup': ['доступ', 'доступ_'],
        'bezopasnost': ['безопасность', 'безопасн_'],
        'pozharnaya': ['пожарная', 'пожарн_'],
        'evakuaciya': ['эвакуация', 'эвакуац_'],
        'dymoudalenie': ['дымоудаление', 'дымоудален_'],
        'vodosnabzhenie': ['водоснабжение', 'водоснабжен_'],
        'kanalizaciya': ['канализация', 'канализац_'],
        'otoplenie': ['отопление', 'отоплен_'],
        'ventilyaciya': ['вентиляция', 'вентиляц_'],
        'gazosnabzhenie': ['газоснабжение', 'газоснабжен_'],
        'elektrosnabzhenie': ['электроснабжение', 'электроснабжен_'],
        'stroitelstvo': ['строительство', 'строител_'],
        'montazh': ['монтаж', 'монтаж_'],
        'rekonstrukciya': ['реконструкция', 'реконстр_'],
        'kapitalni': ['капитальный', 'капитал_'],
        'remontni': ['ремонтный', 'ремонтн_'],
        'tekushchi': ['текущий', 'текущ_'],
        'kapitalni': ['капитальный', 'капитал_'],
        'sredni': ['средний', 'средн_'],
        'tekushchi': ['текущий', 'текущ_'],
        'proektirovanie': ['проектирование', 'проектирован_'],
        'stroitelni': ['строительный', 'строительн_'],
        'montazhni': ['монтажный', 'монтажн_'],
        'puskonaladochni': ['пусконаладочный', 'пусконаладочн_'],
        'ekspluataciya': ['эксплуатация', 'эксплуатац_'],
        'tehnicheski': ['технический', 'техническ_'],
        'tehnologicheski': ['технологический', 'технологическ_'],
        'organizacionni': ['организационный', 'организац_'],
        'ekonomicheski': ['экономический', 'экономическ_'],
        'finansovi': ['финансовый', 'финансов_'],
        'dogovorni': ['договорной', 'договорн_'],
        'zakonodatelni': ['законодательный', 'законодательн_'],
        'normativni': ['нормативный', 'нормативн_'],
        'tehnicheski': ['технический', 'техническ_'],
        'raschetni': ['расчетный', 'расчетн_'],
        'geologicheski': ['геологический', 'геологическ_'],
        'geodezicheski': ['геодезический', 'геодезическ_'],
        'genezicheski': ['генизический', 'генизическ_'],
        'gidrotehnicheski': ['гидротехнический', 'гидротехническ_'],
        'metallurgicheski': ['металлургический', 'металлургическ_'],
        'himicheski': ['химический', 'химическ_'],
        'biologicheski': ['биологический', 'биологическ_'],
        'ecologicheski': ['экологический', 'экологическ_'],
        'zamechaniya': ['замечание', 'замечания', 'замеч_'],
        'otvet': ['ответ', 'ответы', 'ответ_'],
        'zaklyuchenie': ['заключение', 'заключен_'],
        'dogovor': ['договор', 'дог_'],
        'soglashenie': ['соглашение', 'соглаш_'],
        'akt': ['акт', 'акт_'],
        'spravka': ['справка', 'справ_'],
        'svidetelstvo': ['свидетельство', 'свидетельств_'],
        'udostoverenie': ['удостоверение', 'удостоверен_'],
        'licenziya': ['лицензия', 'лиценз_'],
        'svidetelstvo': ['свидетельство', 'свидетельств_'],
        'pasport': ['паспорт', 'пасп_'],
        'shema': ['схема', 'сх_'],
        'plan': ['план', 'пл_'],
        'chertezh': ['чертеж', 'чертеж_'],
        'risunok': ['рисунок', 'рисунок_'],
        'grafik': ['график', 'график_'],
        'tablitsa': ['таблица', 'таблиц_'],
        'spisok': ['список', 'спис_'],
        'otchet': ['отчет', 'отчет_'],
        'protokol': ['протокол', 'протокол_'],
        'reshenie': ['решение', 'решен_'],
        'prikaz': ['приказ', 'приказ_'],
        'rasporyazhenie': ['распоряжение', 'распоряжен_'],
        'ukaz': ['указ', 'указ_'],
        'postanovlenie': ['постановление', 'постановлен_'],
        'zakon': ['закон', 'закон_'],
        'kodeks': ['кодекс', 'кодекс_'],
        'instrukciya': ['инструкция', 'инструкц_'],
        'polozhenie': ['положение', 'положен_'],
        'pravila': ['правила', 'правил_'],
        'normi': ['нормы', 'норм_'],
        'standart': ['стандарт', 'стандарт_'],
        'gost': ['гост', 'гост_'],
        'snip': ['снип', 'снип_'],
        'sp': ['сп', 'сп_'],
        'tu': ['ту', 'ту_'],
        'rd': ['рд', 'рд_'],
        'gd': ['гд', 'гд_'],
        'd': ['д', 'д-'],
        'p': ['п', 'п-'],
        'kr': ['кр', 'кр_'],
        'ks': ['кс', 'кс_'],
        'tm': ['тм', 'тм_'],
        'tr': ['тр', 'тр_'],
        'kr': ['кр', 'кр_'],
        'kp': ['кп', 'кп_'],
        'kv': ['кв', 'кв_'],
        'ko': ['ко', 'ко_'],
        'ar': ['ар', 'ар_'],
        'as': ['ас', 'ас_'],
        'ad': ['ад', 'ад_'],
        'td': ['тд', 'тд_'],
        'mr': ['мр', 'мр_'],
        'gk': ['гк', 'гк_'],
        'oo': ['оо', 'оо_'],
        'za': ['за', 'за_'],
        'ip': ['ип', 'ип_'],
        'ao': ['ао', 'ао_'],
        'oao': ['оао', 'оао_'],
        'pao': ['пао', 'пао_'],
        'gup': ['гуп', 'гуп_'],
        'gbu': ['гбу', 'гбу_'],
        'mup': ['муп', 'муп_'],
        'gu': ['гу', 'гу_'],
        'mk': ['мк', 'мк_'],
        'msp': ['мсп', 'мсп_'],
        'mfc': ['мфц', 'мфц_'],
        'mnp': ['мнп', 'мнп_'],
        'sz': ['сз', 'сз_'],
        'szr': ['сзр', 'сзр_'],
        'uz': ['уз', 'уз_'],
        'uo': ['уо', 'уо_'],
        'uoo': ['уоо', 'уоо_'],
        'zao': ['зао', 'зао_'],
        'ooo': ['ооо', 'ооо_'],
        'ip': ['ип', 'ип_'],
        'fce': ['фцэ', 'фцэ_'],
        'mbu': ['мбу', 'мбу_'],
        'dsk': ['дск', 'дск_'],
        'dk': ['дк', 'дк_'],
        'dku': ['дку', 'дку_'],
        'ku': ['ку', 'ку_'],
        'ktu': ['кту', 'кту_'],
        'msp': ['мсп', 'мсп_'],
        'snt': ['снт', 'снт_'],
        'snpk': ['снпк', 'снпк_'],
        'dnp': ['днп', 'днп_'],
        'nd': ['нд', 'нд_'],
        'tdd': ['тдд', 'тдд_'],
        'td': ['тд', 'тд_'],
        'tdr': ['тдр', 'тдр_'],
        'tr': ['тр', 'тр_'],
        'tkr': ['ткр', 'ткр_'],
        'os': ['ос', 'ос_'],
        'oos': ['оос', 'оос_'],
        'pd': ['пд', 'пд_'],
        'pir': ['пир', 'пир_'],
        'id': ['ид', 'ид_'],
        'td': ['тд', 'тд_'],
        'tm': ['тм', 'тм_'],
        'gm': ['гм', 'гм_'],
        'msu': ['мсу', 'мсу_'],
        'mgsu': ['мгсу', 'мгсу_'],
        'mis': ['мис', 'мис_'],
        'mgsn': ['мгсн', 'мгсн_'],
        'mgsoe': ['мгсоэ', 'мгсоэ_'],
        'gipro': ['гипро', 'гипро_'],
        'giprostroi': ['гипрострой', 'гипрострой_'],
        'lenprom': ['лентроп', 'лентроп_'],
        'gipro': ['гипро', 'гипро_'],
        'mosproject': ['моспроект', 'моспроект_'],
        'mosinzhproekt': ['мосинжпроект', 'мосинжпроект_'],
        'stroiproekt': ['стройпроект', 'стройпроект_'],
        'inzhproekt': ['инжпроект', 'инжпроект_'],
        'giprotrans': ['гипротранс', 'гипротранс_'],
        'giprovod': ['гипровод', 'гипровод_'],
        'giprogaz': ['гипрогаз', 'гипрогаз_'],
        'giproenergo': ['гипроэнерго', 'гипроэнерго_'],
        'giprosvyaz': ['гипросвязь', 'гипросвяз_'],
        'giprogor': ['гипрогор', 'гипрогор_'],
        'giprodor': ['гипродор', 'гипродор_'],
        'gipromost': ['гипромост', 'гипромост_'],
        'giprosnab': ['гипроснаб', 'гипроснаб_'],
        'giprospec': ['гипроспец', 'гипроспец_'],
        'giproteh': ['гипротех', 'гипротех_'],
        'gipromezh': ['гипромеж', 'гипромеж_'],
        'giprostroymash': ['гипростроймаш', 'гипростроймаш_'],
        'stroymechanizaciya': ['строймеханизация', 'строймеханизац_'],
        'stroidetal': ['стройдеталь', 'стройдетал_'],
        'stroymaterial': ['стройматериал', 'стройматериал_'],
        'stroikomplekt': ['стройкомплект', 'стройкомплект_'],
        'stroiservis': ['стройсервис', 'стройсервис_'],
        'stroi': ['строй', 'строй_'],
        'stroit': ['строит', 'строит_'],
        'stroika': ['стройка', 'стройк_'],
        'stroimaterial': ['стройматериал', 'стройматериал_'],
        'stroitekh': ['стройтех', 'стройтех_'],
        'stroitel': ['строитель', 'строител_'],
        'stroitelstvo': ['строительство', 'строител_'],
        'stroi': ['строй', 'строй_'],
        'mos': ['мос', 'мос_'],
        'moskva': ['москва', 'москв', 'мск'],
        'moskovskiy': ['московский', 'московск'],
        'ul': ['ул', 'ул_', 'улица'],
        'bulvar': ['бульвар', 'бульв_'],
        'prospekt': ['проспект', 'проспект_'],
        'shosse': ['шоссе', 'шосс_'],
        'doroga': ['дорога', 'дорог_'],
        'pereulok': ['переулок', 'переул_'],
        'proezd': ['проезд', 'проезд_'],
        'ploshad': ['площадь', 'площад_'],
        'mikrorayon': ['микрорайон', 'микрорайон_'],
        'rayon': ['район', 'район_'],
        'okrug': ['округ', 'округ_'],
        'gorod': ['город', 'город_'],
        'poselok': ['поселок', 'поселок_'],
        'derevnya': ['деревня', 'деревн_'],
        'snt': ['снт', 'снт_'],
        'kp': ['кп', 'кп_'],
        'ls': ['лс', 'лс_'],
        'sk': ['ск', 'ск_'],
        'kv': ['кв', 'кв_'],
        'd': ['д', 'д_', 'дом'],
        'k': ['к', 'к_', 'корпус'],
        'str': ['стр', 'стр_', 'строение'],
        'v': ['в', 'в_', 'вариант'],
        'iz': ['из', 'из_', 'изменение'],
        'red': ['ред', 'ред_', 'редакция'],
        'kor': ['кор', 'кор_', 'корректировка'],
        'nov': ['нов', 'нов_', 'новый'],
        'star': ['стар', 'стар_', 'старый'],
        'aktual': ['актуал', 'актуал_', 'актуальный'],
        'arhiv': ['архив', 'архив_'],
        'rab': ['раб', 'раб_', 'рабочий'],
        'proekt': ['проект', 'проект_'],
        'chert': ['черт', 'черт_', 'чертеж'],
        'ris': ['рис', 'рис_', 'рисунок'],
        'skan': ['скан', 'скан_', 'сканировка'],
        'kop': ['коп', 'коп_', 'копия'],
        'orig': ['ориг', 'ориг_', 'оригинал'],
        'svod': ['свод', 'свод_', 'сводный'],
        'uch': ['уч', 'уч_', 'участок'],
        'uchet': ['учет', 'учет_'],
        'teh': ['тех', 'тех_', 'технический'],
        'pas': ['пас', 'пас_', 'паспорт'],
        'sved': ['свед', 'свед_', 'сведения'],
        'perv': ['перв', 'перв_', 'первичный'],
        'vtor': ['втор', 'втор_', 'вторичный'],
        'tret': ['трет', 'трет_', 'третичный'],
        'chet': ['чет', 'чет_', 'четвертый'],
        'pyat': ['пят', 'пят_', 'пятый'],
        'shest': ['шест', 'шест_', 'шестой'],
        'sem': ['сем', 'сем_', 'седьмой'],
        'vos': ['вос', 'вос_', 'восьмой'],
        'devyat': ['девят', 'девят_', 'девятый'],
        'desyat': ['десят', 'десят_', 'десятый'],
        'odin': ['один', 'один_', '1'],
        'dva': ['два', 'два_', '2'],
        'tri': ['три', 'три_', '3'],
        'chetire': ['четыре', 'четыре_', '4'],
        'pyat': ['пять', 'пять_', '5'],
        'shest': ['шесть', 'шесть_', '6'],
        'sem': ['семь', 'семь_', '7'],
        'vosem': ['восемь', 'восемь_', '8'],
        'devyat': ['девять', 'девять_', '9'],
        'desyat': ['десять', 'десять_', '10'],
        'odinnadcat': ['одиннадцать', 'одиннадцат_', '11'],
        'dvenadcat': ['двенадцать', 'двенадцат_', '12'],
        'trinadcat': ['тринадцать', 'тринадцат_', '13'],
        'chetirnadcat': ['четырнадцать', 'четырнадцат_', '14'],
        'pyatnadcat': ['пятнадцать', 'пятнадцат_', '15'],
        'shestnadcat': ['шестнадцать', 'шестнадцат_', '16'],
        'semnadcat': ['семнадцать', 'семнадцат_', '17'],
        'vosemnadcat': ['восемнадцать', 'восемнадцат_', '18'],
        'devyatnadcat': ['девятнадцать', 'девятнадцат_', '19'],
        'dvadcat': ['двадцать', 'двадцат_', '20'],
        'tridcat': ['тридцать', 'тридцат_', '30'],
        'sorok': ['сорок', 'сорок_', '40'],
        'pyatdesyat': ['пятьдесят', 'пятьдесят_', '50'],
        'shestdesyat': ['шестьдесят', 'шестьдесят_', '60'],
        'semdesyat': ['семьдесят', 'семьдесят_', '70'],
        'vosemdesyat': ['восемьдесят', 'восемьдесят_', '80'],
        'devyanosto': ['девяносто', 'девяност_', '90'],
        'sto': ['сто', 'сто_', '100'],
        'dvisti': ['двести', 'двести_', '200'],
        'trista': ['триста', 'триста_', '300'],
        'chetiresta': ['четыреста', 'четыреста_', '400'],
        'pyatsot': ['пятьсот', 'пятьсот_', '500'],
        'shestsot': ['шестьсот', 'шестьсот_', '600'],
        'semsot': ['семьсот', 'семьсот_', '700'],
        'vosemsot': ['восемьсот', 'восемьсот_', '800'],
        'devyatsot': ['девятьсот', 'девятьсот_', '900'],
        'tisyacha': ['тысяча', 'тысяч_', '1000'],
        'god': ['год', 'год_', 'г'],
        'mesyac': ['месяц', 'месяц_', 'м'],
        'den': ['день', 'день_', 'д'],
        'chas': ['час', 'час_', 'ч'],
        'minuta': ['минута', 'минут_', 'мин'],
        'sekunda': ['секунда', 'секунд_', 'сек'],
        'janvar': ['январь', 'январ_', 'янв'],
        'fevral': ['февраль', 'феврал_', 'фев'],
        'mart': ['март', 'март_', 'мар'],
        'aprel': ['апрель', 'апрел_', 'апр'],
        'may': ['май', 'май_'],
        'iyun': ['июнь', 'июнь_', 'июн'],
        'iyul': ['июль', 'июль_', 'июл'],
        'avgust': ['август', 'август_', 'авг'],
        'sentyabr': ['сентябрь', 'сентябр_', 'сен'],
        'oktyabr': ['октябрь', 'октябр_', 'окт'],
        'noyabr': ['ноябрь', 'ноябр_', 'ноя'],
        'dekabr': ['декабрь', 'декабр_', 'дек'],
        'god': ['г', 'г.', 'год'],
        'invoice': ['invoice', 'invoice_'],
        'estimate': ['estimate', 'estimate_'],
        'contract': ['contract', 'contract_'],
        'project': ['project', 'project_'],
        'passport': ['passport', 'passport_']
    }
    
    def __init__(self, credentials_path: str, target_folder_id: str):
        self.credentials_path = credentials_path
        self.target_folder_id = target_folder_id
        self.service = None
        self.stats = {
            'folders_scanned': 0,
            'files_analyzed': 0,
            'api_calls': 0,
            'errors': 0
        }
        
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API using OAuth 2.0"""
        if not GOOGLE_DRIVE_AVAILABLE:
            logger.error("Google Drive libraries not available")
            return False
        
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.TOKEN_FILE):
            try:
                with open(self.TOKEN_FILE, 'r') as token:
                    creds = Credentials.from_authorized_user_info(json.load(token))
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Could not load token: {e}")
                creds = None
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if not os.path.exists(self.credentials_path):
                logger.error(f"OAuth credentials file not found: {self.credentials_path}")
                return False
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save credentials for future use
                with open(self.TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                    
                logger.info("OAuth authentication successful, token saved")
            except Exception as e:
                logger.error(f"OAuth authentication failed: {e}")
                return False
        
        try:
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Successfully authenticated with Google Drive API via OAuth")
            return True
        except Exception as e:
            logger.error(f"Failed to build Drive service: {e}")
            return False
    
    def list_accessible_folders(self) -> List[Dict[str, Any]]:
        """List all accessible folders"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q="mimeType='application/vnd.google-apps.folder'",
                fields='files(id,name)',
                pageSize=100,
                supportsAllDrives=self.SUPPORTS_ALL_DRIVES,
                includeItemsFromAllDrives=True
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing accessible folders: {e}")
            self.stats['errors'] += 1
            return []
    
    def get_folder_info(self, folder_id: str) -> Optional[Dict[str, Any]]:
        """Get folder metadata"""
        try:
            self.stats['api_calls'] += 1
            folder = self.service.files().get(
                fileId=folder_id,
                fields='id,name,createdTime,modifiedTime,size',
                supportsAllDrives=self.SUPPORTS_ALL_DRIVES
            ).execute()
            
            return {
                'id': folder['id'],
                'name': folder['name'],
                'created_time': folder.get('createdTime'),
                'modified_time': folder.get('modifiedTime'),
                'size': folder.get('size', 0)
            }
        except HttpError as e:
            logger.error(f"Error getting folder info: {e}")
            self.stats['errors'] += 1
            return None
    
    def list_subfolders(self, folder_id: str) -> List[Dict[str, Any]]:
        """List subfolders in a folder"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
                fields='files(id,name,createdTime,modifiedTime,size)',
                pageSize=100,
                supportsAllDrives=self.SUPPORTS_ALL_DRIVES,
                includeItemsFromAllDrives=True
            ).execute()
            
            self.stats['folders_scanned'] += len(results.get('files', []))
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing subfolders: {e}")
            self.stats['errors'] += 1
            return []
    
    def list_files(self, folder_id: str) -> List[Dict[str, Any]]:
        """List files in a folder"""
        try:
            self.stats['api_calls'] += 1
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'",
                fields='files(id,name,mimeType,createdTime,modifiedTime,size,version)',
                pageSize=100,
                supportsAllDrives=self.SUPPORTS_ALL_DRIVES,
                includeItemsFromAllDrives=True
            ).execute()
            
            self.stats['files_analyzed'] += len(results.get('files', []))
            return results.get('files', [])
            
        except HttpError as e:
            logger.error(f"Error listing files: {e}")
            self.stats['errors'] += 1
            return []
    
    def categorize_file_type(self, filename: str, mime_type: str) -> str:
        """Categorize file by type"""
        filename_lower = filename.lower()
        ext = Path(filename).suffix.lower()
        
        for category, extensions in self.FILE_TYPE_CATEGORIES.items():
            if ext in extensions:
                return category
        
        return 'other'
    
    def infer_document_type(self, filename: str) -> str:
        """Infer document type from filename.

        Longer keywords win over short abbreviations so that e.g. "паспорт"
        is not classified as "sp" just because that keyword is checked first.
        """
        filename_lower = filename.lower()

        keyword_pairs = [
            (keyword, doc_type)
            for doc_type, keywords in self.DOCUMENT_TYPE_KEYWORDS.items()
            for keyword in keywords
        ]
        keyword_pairs.sort(key=lambda pair: len(pair[0]), reverse=True)

        for keyword, doc_type in keyword_pairs:
            if keyword and keyword in filename_lower:
                return doc_type

        return 'unknown'
    
    def analyze_file(self, file_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze file metadata"""
        filename = file_metadata['name']
        mime_type = file_metadata['mimeType']
        
        return {
            'id': file_metadata['id'],
            'name': filename,
            'mime_type': mime_type,
            'file_type_category': self.categorize_file_type(filename, mime_type),
            'document_type': self.infer_document_type(filename),
            'size': file_metadata.get('size', 0),
            'created_time': file_metadata.get('createdTime'),
            'modified_time': file_metadata.get('modifiedTime'),
            'has_version': file_metadata.get('version') is not None
        }


def test_oauth_access():
    """Test OAuth Google Drive access"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    credentials_path = os.getenv('GOOGLE_DRIVE_OAUTH_CREDENTIALS_PATH', 'config/oauth_credentials.json')
    target_folder_id = os.getenv('GOOGLE_DRIVE_TARGET_FOLDER_ID')
    
    if not credentials_path:
        print("Error: GOOGLE_DRIVE_OAUTH_CREDENTIALS_PATH not set in .env")
        return False
    
    scanner = OAuthDriveScanner(credentials_path, target_folder_id or "")
    
    print("Starting OAuth authentication...")
    print("A browser window will open. Please authorize the application.")
    
    if not scanner.authenticate():
        print("Error: OAuth authentication failed")
        return False
    
    print("OAuth authentication successful!")
    
    # Try to list accessible folders
    print("\nListing accessible folders...")
    folders = scanner.list_accessible_folders()
    print(f"Accessible folders: {len(folders)}")
    
    if folders:
        print("All accessible folders:")
        for i, folder in enumerate(folders):
            print(f"  {i+1}. {folder['name']} (ID: {folder['id']})")
        
        print("\nPlease select a folder by number or provide the exact folder ID:")
        print("Or press Enter to try the target folder ID from .env")
        
        try:
            selection = input("Selection: ").strip()
            
            if selection.isdigit():
                folder_idx = int(selection) - 1
                if 0 <= folder_idx < len(folders):
                    target_folder_id = folders[folder_idx]['id']
                    print(f"Selected folder: {folders[folder_idx]['name']} (ID: {target_folder_id})")
                else:
                    print("Invalid selection")
                    return False
            elif selection:
                target_folder_id = selection
                print(f"Using provided folder ID: {target_folder_id}")
        except (EOFError, KeyboardInterrupt):
            print("\nUsing target folder ID from .env")
    
    # Try to access target folder
    if target_folder_id:
        print(f"\nTrying to access target folder ID: {target_folder_id}")
        folder_info = scanner.get_folder_info(target_folder_id)
        
        if folder_info:
            print(f"Successfully accessed target folder!")
            print(f"   Folder Name: {folder_info['name']}")
            print(f"   Folder ID: {folder_info['id']}")
            print(f"   Created: {folder_info['created_time']}")
            print(f"   Modified: {folder_info['modified_time']}")
            
            # Test listing subfolders
            subfolders = scanner.list_subfolders(target_folder_id)
            print(f"   Subfolders found: {len(subfolders)}")
            
            # Test listing files
            files = scanner.list_files(target_folder_id)
            print(f"   Files found: {len(files)}")
            
            if subfolders:
                print(f"   First subfolder: {subfolders[0]['name']}")
            
            if files:
                print(f"   First file: {files[0]['name']}")
            
            print(f"\nUpdate .env with: GOOGLE_DRIVE_TARGET_FOLDER_ID={target_folder_id}")
            return True
        else:
            print("Error: Could not access target folder")
            return False
    else:
        print("No target folder ID provided")
        return False


if __name__ == "__main__":
    test_oauth_access()