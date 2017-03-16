# -*- coding: utf-8 -*-
"""Grabs battle chip data from relevant wiki pages and source files.  For
further documentation, reference the README.md.
"""
from __future__ import absolute_import

import os
import re
import csv
import pprint

import scrapy
from scrapy.loader.processors import TakeFirst

def _create_indice(chip):
    """Account for missing indices (Duo and PrixPowr) and create them.
    
    Even if these indices do not actually exist, we still need one for 
    relational data purposes.
    """
    if not chip['game'] == 'bn4':
        # Nothing to do here.
        return chip['indice']

    indice = chip['indice']
    if indice == '??':
        if chip['name'] == 'PrixPowr':
            indice = '39'
        if chip['name'] == 'Duo':
            indice = '40'
    return indice

def _create_key(chip):
    """To prevent any clashes, format the dict keys using the first letter of
    the chip classification, indice, and version if applicable.  To prevent any
    clashes, secret chips will use the letter z.
    """
    try:
        suffix = chip['version'][0]
    except IndexError:
        suffix = ''

    if chip['classification'] == 'secret':
        classification = 'z'
    else:
        classification = chip['classification'][0]

    return '%s-%s%s%s' % (chip['game'], classification, chip['indice'], suffix)

def parsecsv(game):
    """This function accomplishes the same thing as `parsefaq`, only
    difference being that instead of downloading a page and parsing it with
    RegEx, we are using a CSV file.

    The columns, including their key when called, are like so:

        [0] Library ID
        [1] Game ID
        [2] Name (English)
        [3] Name (Japanese)
        [4] Codes
        [5] Damage
        [6] Element
        [7] Rarity
        [8] MB
        [9] Category
        [10] Version (BN3+ only)
    """
    filepath = os.path.join(
        os.path.dirname(__file__),
        'sources',
        'csv',
        '%s.csv' % (game,)
    )

    with open(filepath) as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        chips = {}

        for row in reader:
            chip = {
                'indice': row[0],
                'indice_game': row[1],
                'game': game,
                'name': row[2],
                'name_jp': row[3],
                'codes': set(list(row[4])),
                'damage': row[5],
                'element': row[6],
                'rarity': row[7],
                'size': row[8],
                'classification': row[9].lower()
            }

            if chip['indice_game'] == '?' or chip['classification'] == 'pa':
                    continue

            try:
                chip['version'] = row[10].lower()

                if chip['version'] == 'both':
                    chip['version'] = ''
            except IndexError:
                # No versions pre-BN3
                chip['version'] = ''

            # Instead of adding symbols or other non-cohesive data, we'll
            # either fill in the fields or leave them blank.
            if chip['size'] == '-':
                chip['size'] = ''

            if chip['rarity'] == '?':
                chip['rarity'] = 5

            if chip['size'] == '?':
                chip['size'] = 99

            if chip['indice_game'] in set(['??', '???']):
                chip['indice_game'] = ''

            if game in set(['bn1', 'bn2']):
                if chip['classification'] == 'oss':
                    # OSS chips are excluded.
                    continue

                chip['classification'] = 'standard'

            chip['indice'] = _create_indice(chip)

            chip_key = _create_key(chip)
            chips[chip_key] = chip

    return chips

class ChipsItem(scrapy.Item):
    default_output_processor = TakeFirst()

    indice = scrapy.Field()
    indice_game = scrapy.Field()
    name = scrapy.Field()
    name_jp = scrapy.Field()
    description = scrapy.Field()
    element = scrapy.Field()
    size = scrapy.Field()
    codes = scrapy.Field()
    classification = scrapy.Field()
    damage = scrapy.Field()
    rarity = scrapy.Field()
    game = scrapy.Field()
    version = scrapy.Field()

class FormatterPipeline(object):
    """Formats data properly after `MegaSpider.parse` has yielded data.
    """

    def process_item(self, item, spider):
        # Rename elements to fit in with chiplibrary naming conventions.
        item['element'] = item['element'] \
            .replace('none', 'null') \
            .replace('break', 'breaking') \
            .replace('invis', 'invisible') \
            .replace('elec', 'electric') \
            .replace('num', 'plus') \
            .replace('obj', 'obstacle') \
            .replace('recov', 'recovery') \
            .replace('ground', 'terrain') \
            .replace('search', 'cursor')

        if item['damage']:
            # MMBN and OSS have the same chips. We don't care about the
            # OSS data, so ignore it.
            if item['game'] == 'bn1' and item['damage']:
                power_re = re.compile(r'([0-9]+)\s\(MMBN\)')
                result_re = power_re.match(item['damage'])
                if result_re:
                    item['damage'] = result_re.group(1)
            item['damage'] = item['damage'].strip()
            # Variable damage
            if item['damage'] == '????' or item['damage'] == '???':
                item['damage'] = '-1'
            # Damage ranges, if available.
            if '-' in item['damage'].replace('~', '-'):
                item['damage'] = item['damage'].split('-')[0]
            else:
                item['damage'] = [item['damage']]

        item['description'] = item['description'].strip()
        return item

class MegaSpider(scrapy.Spider):
    """The main spider class, inheriting from `scrapy.Spider` class.  Scrapes
    MMKB (megaman.wikia.com/) battle chip list pages, and grabs any missing
    attributes from game FAQs online, and from the local CSV sources.
    """
    name = 'chiplibrary'
    allowed_domains = ['megaman.wikia.com']

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'FEED_URI': 'dumps/chips.xml',
        'FEED_FORMAT': 'xml',
        'ITEM_PIPELINES': {
            'spider.FormatterPipeline': 1
        },
        'LOG_FILE': 'log',
        'LOG_ENABLED': True,
        'LOG_STDOUT': True
    }

    xpaths = {
        'bn1': {
            'table': '//*[@id="mw-content-text"]/table[1]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[4]/text()',
            'description': 'td[5]/text()'
        },
        'bn2': {
            'table': '//*[@id="mw-content-text"]/table[1]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[5]/text()',
            'description': 'td[8]/text()'
        },
        'bn3': {
            'table': '//*[@id="mw-content-text"]/table[position()>=1 and position()<4]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[4]/text()',
            'description': 'td[7]/text()',
            'exclusives': {
                'blue': set([
                    'FoldrBak',
                    'Bass+',
                    'DarkAura',
                    'DeltaRay',
                    'AlphArm\u03A9'
                ]),
                'white': set([
                    'NaviRcycl',
                    'Bass',
                    'Serenade',
                    'Balance',
                    'AlphArm\u03A3'
                ])
            }
        },
        'bn4': {
            'table': '//*[@id="mw-content-text"]/table[position()>=2 and position()<6]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[5]/text()',
            'description': 'td[6]/text()',
            'exclusives': {
                'redsun': set([
                    'Roll',
                    'RollSP',
                    'RollDS',
                    'GutsMan',
                    'GutsMnSP',
                    'GutsMnDS',
                    'WindMan',
                    'WindMnSP',
                    'WindMnDS',
                    'SerchMan',
                    'SrchMnSP',
                    'SrchMnDS',
                    'FireMan',
                    'FireMnSP',
                    'FireMnDS',
                    'ThunMan',
                    'ThunMnSP',
                    'ThunMnDS',
                    'RedSun',
                    'Bass',
                    'HolyDrem',
                    'Bass',
                    'BugCharg',
                    'BlakBarr'
                ]),
                'bluemoon': set([
                    'ProtoMan',
                    'ProtoMSP',
                    'ProtoMDS',
                    'NumbrMan',
                    'NumbMnSP',
                    'NumbMnDS',
                    'MetalMan',
                    'MetlMnSP',
                    'MetlMnDS',
                    'JunkMan',
                    'JunkMnSP',
                    'JunkMnDS',
                    'AquaMan',
                    'AquaMnSP',
                    'AquaMnDS',
                    'WoodMan',
                    'WoodMnSP',
                    'WoodMnDS',
                    'BlueMoon',
                    'SignlRed',
                    'BassAnly',
                    'BugCurse',
                    'DeltaRay'
                ])
            }
        },
        'bn5': {
            'table': '//*[@id="mw-content-text"]/table[position()>=1 and position()<6]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[5]/text()',
            'description': 'td[6]/text()',
            'exclusives': {
                'colonel': set([
                    'Colonel',
                    'ColonelSP',
                    'ColonelDS',
                    'ShadoMan',
                    'ShadoMnSP',
                    'ShadoMnDS',
                    'NumbrMan',
                    'NumbrMnSP',
                    'NumbrMnDS',
                    'TmhwkMan',
                    'TmhwkMnSP',
                    'TmhwkMnDS',
                    'KnightMan',
                    'KnigtMnSP',
                    'KnigtMnDS',
                    'ToadMan',
                    'ToadMnSP',
                    'ToadMnDS',
                    'CrossDiv',
                    'MetrKnuk',
                    'BassAnly',
                    'OmegaRkt',
                    'BugCharg',
                    'Phoenix'
                ]),
                'protoman': set([
                    'ProtoMan',
                    'ProtoMnSP',
                    'ProtoMnDS',
                    'GyroMan',
                    'GyroMnSP',
                    'GyroMnDS',
                    'SearchMan',
                    'SearchMnSP',
                    'SearchMnDS',
                    'NapalmMan',
                    'NapalmMnSP',
                    'NapalmMnDS',
                    'MagnetMan',
                    'MagnetMnSP',
                    'MagnetMnDS',
                    'Meddy',
                    'MeddySP',
                    'MeddyDS',
                    'DeltaRay',
                    'BigHook',
                    'Bass',
                    'HolyDrem',
                    'BugCurse',
                    'DethPhnx'
                ]),
                'doubleteam': set([
                    'LeaderR',
                    'ChaosLrd'
                ]),
            }
        },
        'bn6': {
            'table': '//*[@id="mw-content-text"]/table[position()>=1 and position()<4]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[5]/text()',
            'description': 'td[6]/text()',
            'exclusives': {
                'falzar': set([
                    'SpoutMan',
                    'SpoutMnEX',
                    'SpoutMnSP',
                    'TmhkMan',
                    'TmhkManEX',
                    'TmhkManSP',
                    'TenguMan',
                    'TenguMnEX',
                    'TenguMnSP',
                    'GrndMan',
                    'GrndManEX',
                    'GrndManSP',
                    'DustMan',
                    'DustManEX',
                    'DustManSP',
                    'BassAnly',
                    'MetrKnuk',
                    'CrossDiv',
                    'HubBatc',
                    'BgDthThd'
                ]),
                'gregar': set([
                    'HeatMan',
                    'HeatManEX',
                    'HeatManSP',
                    'ElecMan',
                    'ElecManEX',
                    'ElecManSP',
                    'SlashMan',
                    'SlashMnEX',
                    'SlashMnSP',
                    'ChrgeMan',
                    'ChrgeMnEX',
                    'ChrgeMnSP',
                    'EraseMan',
                    'EraseMnEX',
                    'EraseMnSP',
                    'Bass',
                    'BigHook',
                    'DeltaRay',
                    'ColForce',
                    'BugRSwrd'
                ])
            }
        }
    }

    start_urls = (
        'http://megaman.wikia.com/wiki/List_of_Mega_Man_Battle_Network_Battle_Chips',
        'http://megaman.wikia.com/wiki/List_of_Mega_Man_Battle_Network_2_Battle_Chips',
        'http://megaman.wikia.com/wiki/List_of_Mega_Man_Battle_Network_3_Battle_Chips',
        'http://megaman.wikia.com/wiki/List_of_Mega_Man_Battle_Network_4_Battle_Chips',
        'http://megaman.wikia.com/wiki/List_of_Mega_Man_Battle_Network_5_Battle_Chips',
        'http://megaman.wikia.com/wiki/List_of_Mega_Man_Battle_Network_6_Battle_Chips'
    )

    def parse(self, response):
        request_url = response.request.url
        # Determine what game we're working with so we can decide what XPath
        # rules to use.
        if '2' in request_url:
            curr_game = 'bn2'
        elif '3' in request_url:
            curr_game = 'bn3'
        elif '4' in request_url:
            curr_game = 'bn4'
        elif '5' in request_url:
            curr_game = 'bn5'
        elif '6' in request_url:
            curr_game = 'bn6'
        else:
            curr_game = 'bn1'

        xpaths = self.xpaths[curr_game]
        # Since not all information is present in MMKB, we'll dig up
        # on another FAQ for the rest of the missing information.
        #faq_attrs = parsefaq(curr_game, xpaths)
        # Now, time to parse the CSV extra files.
        csv_attrs = parsecsv(curr_game)

        for table in response.xpath(xpaths['table']):
            for sel in table.xpath('tr[position()>1]'):
                # Make sure we skip the version-exclusive sub-headings.
                if sel.xpath('td[1]/b/text()'):
                    continue

                item = ChipsItem()
                item['game'] = curr_game
                item['description'] = sel.xpath(
                    xpaths['description']
                ).extract_first()
                item['indice'] = sel.xpath(xpaths['indice']).extract_first()
                item['indice'] = item['indice'].lstrip('0')
                # All chips are standard classification by default.
                item['classification'] = 'standard'

                if not curr_game in ('bn1', 'bn2'):
                    item['classification'] = table.xpath(
                        'preceding-sibling::h2[1]/span/text()'
                    ).extract_first().replace(' Chips', '').strip().lower()
                    if not item['classification']:
                        item['classification'] = 'standard'

                # There is probably a hyperlink preventing us from grabbing the
                # chip name.
                name_hyperlink = xpaths['name'] \
                    .replace('/text()', '/a/text()')
                item['name'] = sel.xpath(xpaths['name']).extract_first()
                # Japanese character workaround.
                if (curr_game in set(['bn5', 'bn6'])
                    and sel.xpath(name_hyperlink)
                ):
                    item['name'] = sel.xpath(name_hyperlink).extract_first()
                if not item['name']:
                    item['name'] = sel.xpath(name_hyperlink).extract_first()

                # All chips have no version specified by default.
                item['version'] = ''

                if curr_game == 'bn3':
                    if item['name'] in xpaths['exclusives']['blue']:
                        item['version'] = 'blue'
                    elif item['name'] in xpaths['exclusives']['white']:
                        item['version'] = 'white'
                elif curr_game == 'bn4':
                    if item['name'] in xpaths['exclusives']['redsun']:
                        item['version'] = 'redsun'
                    elif item['name'] in xpaths['exclusives']['bluemoon']:
                        item['version'] = 'bluemoon'
                    # Account for missing indices (Duo and PrixPowr)
                    item['indice'] = _create_indice(item)                        
                elif curr_game == 'bn5':
                    if item['name'] in xpaths['exclusives']['colonel']:
                        item['version'] = 'colonel'
                    elif item['name'] in xpaths['exclusives']['protoman']:
                        item['version'] = 'protoman'
                    elif item['name'] in xpaths['exclusives']['doubleteam']:
                        item['version'] = 'doubleteam'
                elif curr_game == 'bn6':
                    if item['name'] in xpaths['exclusives']['falzar']:
                        item['version'] = 'falzar'
                    elif item['name'] in xpaths['exclusives']['gregar']:
                        item['version'] = 'gregar'

                item['damage'] = sel.xpath(xpaths['damage']).extract_first()
                # Set the missing attributes of a chip using the csv_attrs
                # dict.
                csv_key = _create_key(item)

                item['element'] = csv_attrs[csv_key]['element']
                item['rarity'] = csv_attrs[csv_key]['rarity']
                item['size'] = csv_attrs[csv_key]['size']
                item['codes'] = csv_attrs[csv_key]['codes']
                item['indice_game'] = csv_attrs[csv_key]['indice_game']
                item['name_jp'] = csv_attrs[csv_key]['name_jp']
                # Spit it all out!
                yield item
