# -*- coding: utf-8 -*-
"""Grabs battle chip data from relevant wiki pages and FAQs.  For further
documentation, reference the README.md."""
from __future__ import absolute_import

import re
import urllib.request

import scrapy
from scrapy.loader.processors import TakeFirst

def bn_getattrs(game, info, exclusives):
    """MMKB is missing information such as rarity, elements, chip codes and
    chip sizes for certain chips in the games.  By parsing online game FAQs
    with a regular expression, we can scrape even further for more information.
    """
    
    faq_re = re.compile(info['re'], re.M | re.X | re.I)
    faq_url = info['faq']
    
    req = urllib.request.Request(
        faq_url,
        headers={'User-Agent': 'Mozilla/5.0'}
    )

    with urllib.request.urlopen(req) as resp:
        chips = {}
        resp_read = resp.read() \
            .decode(resp.info().get_content_charset()) \
            .replace('\r\n', '\n')
        re_results = re.findall(faq_re, resp_read)

        for chip in re_results:
            if game == 'bn1':
                element = chip[2].lower() \
                    .replace('water', 'aqua') \
                    .replace('elec', 'electric') \
                    .replace('none', 'null')
                codes = list(chip[5])
                chips[chip[0]] = (element, chip[4], codes)

            if game == 'bn2':
                # Since most of the information for BN2 is intact, all we need
                # is the chip rarity.
                if chip[1] == '-':
                    rarity = '5'
                else:
                    rarity = str(len(chip[1]))
                chips[chip[0]] = (rarity,)
                
            if game == 'bn3':
                # Since there are multiple classifications and different
                # indice numbers, we're going to have to use the chip name
                # as the dict key.
                
                # Fix FAQ typos. :|
                name = chip[0] \
                    .replace('Volcanoe', 'Volcano') \
                    .replace('AntiDamg', 'AntiDmg') \
                    .replace('Ligtning', 'Lightning') \
                    .replace('LifAura', 'LifeAura') \
                    .lower()
                element = chip[1].replace('Elec', 'Electric').lower()
                rarity = str(len(chip[2]))

                chips[name] = (rarity, element)
                
            if game == 'bn4':
                name = chip[0] \
                    .replace('ICEELEM', 'ELEMICE') \
                    .replace('WHITEWEB', 'WHITWEB') \
                    .replace('PNLRETURN', 'PNLRETRN') \
                    .replace('HOLYPNL', 'HOLYPANL') \
                    .replace('ANTIAQUA', 'ANTIWATR') \
                    .replace('COLORPNT', 'COLORPT') \
                    .replace('DBLPNT', 'DBLPOINT') \
                    .replace('GREENWD1', 'GREENWD') \
                    .replace('Z-SAVER', 'Z SAVER') \
                    .replace('GRANDPRIXPOWER', 'PRIXPOWR') \
                    .replace(' (RS)', '') \
                    .replace(' (BM)', '') \
                    .strip() \
                    .lower()
                codes = chip[1]
                size = chip[2]

                chips[name] = (codes, size)
                
            if game == 'bn5':
                # Since the FAQ spells out chip names fully most of the time,
                # and also uses the same indices, we're going to have to use a
                # different naming scheme for the dict keys.
                
                # Shorten version-exclusive chip names from FAQ.
                name_short = chip[2] \
                    .replace('Tomahawk', 'Tmhwk') \
                    .replace('Shadow', 'Shado') \
                    .replace('Number', 'Numbr') \
                    .replace('Protoman', 'ProtoMan') \
                    .replace('Serch', 'Search')
                    
                if 'SP' in name_short or 'DS' in name_short:
                    # Navi Chips are shortened a little differently.
                    name_short = name_short.replace('Knight', 'Knigt')
                    name_short = name_short.replace('Man', 'Mn')
                        
                if name_short in exclusives['colonel']:
                    version = 'c'
                elif name_short in exclusives['protoman']:
                    version = 'p'
                else:
                    version = ''
                # Typos
                indice = chip[1].replace('1116', '116')
                size = chip[4] \
                    .replace('Invisible', '42') \
                    .replace('80</span><span id="faqspan-2">', '80')

                codes = chip[3]
                rarity = str(len(chip[5]))
                chips[u''.join([chip[0], indice, version])] = (
                    codes,
                    size,
                    rarity
                )

            if game == 'bn6':
                codes = chip[1].strip().replace(' ', ',')
                rarity = str(len(chip[2]))
                size = chip[3]
                # Only standard chips are available for now.             
                if len(chips) < 200:
                    chips[chip[0]] = (codes, rarity, size)

        return chips

class ChipsItem(scrapy.Item):
    default_output_processor = TakeFirst()
    
    description = scrapy.Field()
    indice = scrapy.Field()
    name = scrapy.Field()
    element = scrapy.Field()
    size = scrapy.Field()
    codes = scrapy.Field()
    classification = scrapy.Field()
    damage = scrapy.Field()
    rarity = scrapy.Field()
    game = scrapy.Field()
    version = scrapy.Field()

class FormatterPipeline(object):
    """Formats data properly on final output.
    """
    
    def process_item(self, item, spider):
        item['indice'] = item['indice'].lstrip('0')
        
        item['element'] = item['element'] \
            .lower() \
            .replace('bc element ', '') \
            .replace('bc attribute ', '') \
            .replace('typecrack', 'terrain') \
            .replace('typecursor', 'cursor') \
            .replace('typerecover', 'recovery') \
            .replace('type', '') \
            .replace('none', 'null') \
            .replace('heat', 'fire') \
            .replace('break', 'breaking') \
            .replace('invis', 'invisible') \
            .replace('elec', 'electric') \
            .replace('electrictric', 'electric')

        if item['size']:
            item['size'] = item['size'].replace(' MB', '').strip()

        if item['damage']:
            # MMBN and OSS have the same chips. We don't care about the
            # OSS data, so ignore it.
            if item['game'] == 'bn1' and item['damage']:
                power_re = re.compile(u'([0-9]+)\s\(MMBN\)')
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

        if item['codes']:
            # Remove whitespace and convert into a list.
            if not item['game'] == 'bn1':
                item['codes'] = [code.strip() for code in item['codes'].split(',')]
        
        item['description'] = item['description'].strip()
        return item

class MegaSpider(scrapy.Spider):
    name = 'chiplibrary'
    allowed_domains = ['megaman.wikia.com']

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'FEED_URI': 'dumps/chips.xml',
        'FEED_FORMAT': 'xml',
        'ITEM_PIPELINES': {
            'spider.FormatterPipeline': 1
        }
    }

    xpaths = {
        'bn1': {
            'table': '//*[@id="mw-content-text"]/table[1]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[4]/text()',
            'description': 'td[5]/text()',
            'size': '',
            'codes': '',
            'exclusives': '',
            'extra': {
                're': r'''([0-9]+)[\s]+([-\w]+)
                [\s]+([A-Z]+)
                [\s]+([0-9-\???\\+\\*]+)
                [\s]+([\d]+)
                [\s]+([A-Z-\*]+)''',
                'faq': 'https://www.gamefaqs.com/gba/457634-mega-man-battle-network/faqs/30244?print=1'
            }
         },
        'bn2': {
            'table': '//*[@id="mw-content-text"]/table[1]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'element': 'td[4]/a/img/@alt',
            'damage': 'td[5]/text()',
            'codes': 'td[6]/text()',
            'size': 'td[7]/text()',
            'description': 'td[8]/text()',
            'exclusives': {},
            'extra': {
                're': r'''([\d]{3})[\s]{2}[-\w\+]+[\s]+[-\d\?]+[\s]+[\w]+[\s]+([-\*]{1,5})''',
                'faq': 'http://www.ign.com/faqs/2003/mega-man-battle-network-2-walkthroughfaq-391636?print=1'
            }
         },
        'bn3': {
            'table': '//*[@id="mw-content-text"]/table[position()>=1 and position()<4]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'damage': 'td[4]/text()',
            'codes': 'td[5]/text()',
            'size': 'td[6]/text()',
            'description': 'td[7]/text()',
            'exclusives': {
                'blue': (
                    u'FoldrBak',
                    u'Bass+',
                    u'DarkAura',
                    u'DeltaRay',
                    u'AlphArm\u03A9'
                ),
                'white': (
                    u'NaviRcycl',
                    u'Bass',
                    u'Serenade',
                    u'Balance',
                    u'AlphArm\u03A3'
                )
            },
            'extra': {
                're': r'''[0-9]{1,3}\.[\t\s]([-\w\+]+)[\t\s]+[0-9-\?\+]{0,4}[\s]([\w]+)[\s]([\*]{1,5})''',
                'faq': 'http://www.gamefaqs.com/gba/915457-mega-man-battle-network-3-blue/faqs/24086?print=1'
            }
        },
        'bn4': {
            'table': '//*[@id="mw-content-text"]/table[position()>=2 and position()<6]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'element': 'td[4]/a/img/@alt',
            'damage': 'td[5]/text()',
            'size': '',
            'description': 'td[6]/text()',
            'codes': '',
            'exclusives': {
                'redsun': (
                    u'Roll',
                    u'RollSP',
                    u'RollDS',
                    u'GutsMan',
                    u'GutsMnSP',
                    u'GutsMnDS',
                    u'WindMan',
                    u'WindMnSP',
                    u'WindMnDS',
                    u'SerchMan',
                    u'SrchMnSP',
                    u'SrchMnDS',
                    u'FireMan',
                    u'FireMnSP',
                    u'FireMnDS',
                    u'ThunMan',
                    u'ThunMnSP',
                    u'ThunMnDS',
                    u'RedSun',
                    u'Bass',
                    u'HolyDrem',
                    u'Bass',
                    u'BugCharg',
                    u'BlakBarr'
                ),
                'bluemoon': (
                    u'ProtoMan',
                    u'ProtoMSP',
                    u'ProtoMDS',
                    u'NumbrMan',
                    u'NumbMnSP',
                    u'NumbMnDS',
                    u'MetalMan',
                    u'MetlMnSP',
                    u'MetlMnDS',
                    u'JunkMan',
                    u'JunkMnSP',
                    u'JunkMnDS',
                    u'AquaMan',
                    u'AquaMnSP',
                    u'AquaMnDS',
                    u'WoodMan',
                    u'WoodMnSP',
                    u'WoodMnDS',
                    u'BlueMoon',
                    u'SignlRed',
                    u'BassAnly',
                    u'BugCurse',
                    u'DeltaRay'
                )
            },
            'extra': {
                're': r'''[\~]{3}[\s]+[\d]+[\s]([-\w\+\(\)\ ]+)[\s]?[\~]{3}[\n]+
                \-[\w]+:[\s]([*\w\s]+(?:,[\s][*\w]*)*)[\n]+
                \-[\w]+:[\s][0-9-\?\+]+[\n\s]+
                \-[\w \ ]+:[\s][\w\ \/\?]+[\n]+\-[-\w\+\ \/\(\)]+:[\s]+([\d]+)[\s]?MB
                ''',
                'faq': 'http://www.gamefaqs.com/gba/919000-mega-man-battle-network-4-blue-moon/faqs/31235?print=1',
            }
        },
        'bn5': {
            'table': '//*[@id="mw-content-text"]/table[position()>=1 and position()<6]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'element': 'td[4]/a/img/@alt',
            'damage': 'td[5]/text()',
            'codes': 'td[5]/text()',
            'description': 'td[6]/text()',
            'codes': '',
            'size': '',
            'exclusives': {
                'colonel': (
                    u'Colonel',
                    u'ColonelSP',
                    u'ColonelDS',
                    u'ShadoMan',
                    u'ShadoMnSP',
                    u'ShadoMnDS',
                    u'NumbrMan',
                    u'NumbrMnSP',
                    u'NumbrMnDS',
                    u'TmhwkMan',
                    u'TmhwkMnSP',
                    u'TmhwkMnDS',
                    u'KnightMan',
                    u'KnigtMnSP',
                    u'KnigtMnDS',
                    u'ToadMan',
                    u'ToadMnSP',
                    u'ToadMnDS',
                    u'CrossDiv',
                    u'MetrKnuk',
                    u'BassAnly',
                    u'OmegaRkt',
                    u'BugCharg',
                    u'Phoenix'
                ),
                'protoman': (
                    u'ProtoMan',
                    u'ProtoMnSP',
                    u'ProtoMnDS',
                    u'GyroMan',
                    u'GyroMnSP',
                    u'GyroMnDS',
                    u'SearchMan',
                    u'SearchMnSP',
                    u'SearchMnDS',
                    u'NapalmMan',
                    u'NapalmMnSP',
                    u'NapalmMnDS',
                    u'MagnetMan',
                    u'MagnetMnSP',
                    u'MagnetMnDS',
                    u'Meddy',
                    u'MeddySP',
                    u'MeddyDS',
                    u'DeltaRay',
                    u'BigHook',
                    u'Bass',
                    u'HolyDrem',
                    u'BugCurse',
                    u'DethPhnx'
                )
            },
            'extra': {
                're': r'''[-]{18}[\n]
                ([A-Z]{1,2})([0-9]+)\:[\s]?([-\w\+\(\)\s]+)[\n]
                [-]{18}[\n]

                [\w]+:[\s]([*\w\s]+(?:,[\s]?[*\w]*)*)[\s]{0,3}[\n]
                [\w]+:[\s](.*)[\n]
                [\w]+:[\s][-\+\w\s\(\)]+[\s]?[\n]
                [\w]+:[\s]?[\w\s\(\)]+[\n]
                [\w\s]+:[\s]+[-\w\+\(\)\s\.]+
                [\w]+:[\s]([*\w]+)
                ''',
                'faq': 'https://www.gamefaqs.com/ds/928331-mega-man-battle-network-5-double-team/faqs/52952?print=1'
            }
        },
        'bn6': {
            'table': '//*[@id="mw-content-text"]/table[position()>=1 and position()<4]',
            'indice': 'td[1]/text()',
            'name': 'td[3]/text()',
            'element': 'td[4]/a/img/@alt',
            'damage': 'td[5]/text()',
            'description': 'td[6]/text()',
            'size': '',
            'codes': '',
            'exclusives': {
                'falzar': (
                    u'SpoutMan',
                    u'SpoutMnEX',
                    u'SpoutMnSP',
                    u'TmhkMan',
                    u'TmhManEX',
                    u'TmhkManSP',
                    u'TenguMan',
                    u'TenguMnEX',
                    u'TenguMnSP',
                    u'GrndMan',
                    u'GrndManEX',
                    u'GrndManSP',
                    u'DustMan',
                    u'DustManEX',
                    u'DustManSP',
                    u'BassAnly',
                    u'MetrKnuk',
                    u'CrossDiv',
                    u'HubBatc',
                    u'BgDthThd'
                ),
                'gregar': (
                    u'HeatMan',
                    u'HeatManEX',
                    u'HeatManSP',
                    u'ElecMan',
                    u'ElecManEX',
                    u'ElecManSP',
                    u'SlashMan',
                    u'SlashMnEX',
                    u'SlashMnSP',
                    u'ChrgeMan',
                    u'ChrgeMnEX',
                    u'ChrgeMnSP',
                    u'EraseMan',
                    u'EraseMnEX',
                    u'EraseMnSP',
                    u'Bass',
                    u'BigHook',
                    u'DeltaRay',
                    u'ColForce',
                    u'BugRSwrd'
                )
            },
            'extra': {
                're': r'''([\d]{3})\.[\s][\w\+\'\ ]+[\n]
                [\w]+[\:]?[\s]([\w\*\s]+)[\/][\s]?[\w]+:[\s]?([\*]{1,5})[\s][\/][\s][\w]+:[\s][-\w\?\ ]+[\n]
                [\w]+:[\s][\w]+[\s]?[\/][\s][\w]{2}:[\s]([\d]+)''',
                'faq': 'https://www.gamefaqs.com/gba/929993-mega-man-battle-network-6-cybeast-gregar/faqs/40403?print=1'
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
        # Since not all information is present on these FAQs, we'll dig up
        # on another FAQ for the rest of the missing information.
        _bn_attrs = bn_getattrs(curr_game, xpaths['extra'], xpaths['exclusives'])
        
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
                if curr_game in ('bn5', 'bn6') and sel.xpath(name_hyperlink):
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
                elif curr_game == 'bn5':
                    if item['name'] in xpaths['exclusives']['colonel']:
                        item['version'] = 'colonel'
                    elif item['name'] in xpaths['exclusives']['protoman']:
                        item['version'] = 'protoman'
                elif curr_game == 'bn6':                        
                    if item['name'] in xpaths['exclusives']['falzar']:
                        item['version'] = 'falzar'
                    elif item['name'] in xpaths['exclusives']['gregar']:
                        item['version'] = 'gregar'

                if not curr_game in ('bn1', 'bn3'):
                    item['element'] = sel.xpath(
                        xpaths['element']
                    ).extract_first()
                else:
                    item['element'] = ''

                if xpaths['size']:
                    item['size'] = sel.xpath(xpaths['size']).extract_first()
                else:
                    item['size'] = ''

                if xpaths['codes']:
                    item['codes'] = sel.xpath(xpaths['codes']).extract_first()
                else:
                    item['codes'] = ''

                item['damage'] = sel.xpath(xpaths['damage']).extract_first()
                item['rarity'] = ''
                # Hacky solution to missing attributes, but it shall do.
                if curr_game == 'bn1':
                    key = item['indice'].lstrip('0')
                    item['element'] = _bn_attrs[key][0]
                    item['rarity'] = _bn_attrs[key][1]
                    item['codes'] = _bn_attrs[key][2]
                
                if curr_game == 'bn2':
                    item['rarity'] = _bn_attrs[item['indice']][0]
                    
                if curr_game == 'bn3':
                    notincluded = (
                        xpaths['exclusives']['white'] + (
                            u'Punk',
                            u'BassGS',
                            u'AlphArm\u03A9'
                        )
                    )
                    if item['name'] in notincluded:
                        item['rarity'] = '5'
                        item['element'] = 'null'
                    else:
                        key = item['name'].replace(' ', '').lower()
                        item['rarity'] = _bn_attrs[key][0]
                        item['element'] = _bn_attrs[key][1]

                if curr_game == 'bn4':
                    if item['indice'] == '??':
                        if item['name'] == 'PrixPowr':
                            item['indice'] = '39'
                        if item['name'] == 'Duo':
                            item['indice'] = '40'
                    key = item['name'].lower()
                    item['codes'] = _bn_attrs[key][0]
                    item['size'] = _bn_attrs[key][1]

                if curr_game == 'bn5':
                    try:
                        suffix = item['version'][0]
                    except IndexError:
                        suffix = ''
                        
                    key = u''.join([
                        item['classification'][0].upper(),
                        item['indice'].zfill(3),
                        suffix
                    ])
                    if key == 'M028':
                        exit('Numberman is missing: %s' % (suffix,))
                    item['codes'] = _bn_attrs[key][0]
                    item['size'] = _bn_attrs[key][1]
                    item['rarity'] = _bn_attrs[key][2]
                    
                if curr_game == 'bn6':
                    if item['classification'] == 'standard':
                        key = item['indice'].zfill(3)
                        item['codes'] = _bn_attrs[key][0]
                        item['rarity'] = _bn_attrs[key][1]
                        item['size'] = _bn_attrs[key][2]
                # Spit it all out!
                yield item
