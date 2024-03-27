import json
from collections import OrderedDict
from datetime import datetime

from scrapy import Spider, Request


class RightmoveSpider(Spider):
    name = 'rightmove'
    base_url = 'https://www.rightmove.co.uk/'
    # start_urls = [base_url]

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    }

    custom_settings = {
        'CONCURRENT_REQUESTS': 5,
        'FEED_FORMAT': 'xlsx',
        'FEED_EXPORTERS': {'xlsx': 'scrapy_xlsx.XlsxItemExporter'},
        'FEED_URI': f'./rightmove_properties/output/RightMove Properties {datetime.now().strftime("%d%m%Y %H%M%S")}.xlsx',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.property_urls = self.get_property_urls_from_file()

    def start_requests(self):
        for url in self.property_urls:
            yield Request(url=url, headers=self.headers)

    def parse(self, response, **kwargs):
        item = OrderedDict()
        item['Address'] = response.css('[itemprop="streetAddress"] ::text').get('').strip()
        item['Price PCM'] = response.css('article div span:contains(" pcm")::text').get('').replace('pcm', '').strip()
        item['Price PW'] = response.css('article div:contains("pw")::text').get('').replace('pw', '').strip()
        item['Property Type'] = self.get_value_by_heading(response, 'PROPERTY TYPE')
        item['Bedrooms'] = self.get_value_by_heading(response, 'BEDROOMS')
        item['Bathrooms'] = self.get_value_by_heading(response, 'BATHROOMS')
        item['Available Date'] = self.get_value_by_heading(response, 'Let available date:', letting_details=True)
        item['Furnish Type'] = self.get_value_by_heading(response, 'Furnish type:', letting_details=True)
        item.update(self.get_images(response))

        """These Below fields removed by Client"""

        # item['Deposit'] = self.get_value_by_heading(response, 'Deposit:', letting_details=True).replace(',', '').strip()
        # item['Min Tenancy'] = self.get_value_by_heading(response, 'Min. Tenancy:', letting_details=True)
        # item['Let Type'] = self.get_value_by_heading(response, 'Let type:', letting_details=True)
        # item['Council Tax'] = self.get_value_by_heading(response, 'Council Tax:', letting_details=True)
        # item['Agent'] = response.css('article:contains("About the agent") h3 ::text').get('')
        # item['Description'] = '\n\n'.join(response.css('h2:contains("Property description") ~ div div ::text').getall())
        # item['Property URL'] = response.url

        yield item

        a=0

    def get_value_by_heading(self, response, heading, letting_details=False):
        return response.css(f'dl:contains("{heading}") dd ::text').get('').strip().replace('Ã—', '') if not letting_details else response.css(f'dt:contains("{heading}") + dd::text').get('').strip()

    def get_images(self, response):
        try:
            json_data = json.loads(response.css('script:contains("propertyData")::text').re_first(r'window.PAGE_MODEL = (.*)'))
            property_json = json_data.get('propertyData', {}) or {}
            property_images = [image.get('url') for image in property_json.get('images', [{}])]
            floor_plan_image = property_json.get('floorplans', [{}])[0].get('url') or None
        except json.JSONDecodeError:
            floor_plan_image = None
            property_images = []
        except AttributeError:
            floor_plan_image = None
            property_images = []
        except IndexError:
            floor_plan_image = None

        floor_plan = floor_plan_image or response.css('a[href*="plan"] img::attr(src)').get('').replace('_max_296x197', '')
        image_urls = property_images or response.css('a[itemprop="photo"] [itemprop="contentUrl"]::attr(content)').getall()

        images = {f'Image {index}': '' for index in range(1, 11)}

        # return {f'Image {index + 1}': image_url for index, image_url in enumerate(image_urls)}
        images.update({f'Image {index + 1}': f'=IMAGE("{image_url}")' for index, image_url in enumerate(image_urls)})
        images.update({'Floor Plan': f'=IMAGE("{floor_plan}")'})

        return images

    def get_property_urls_from_file(self):
        with open('./rightmove_properties/input/property_urls.txt', mode='r', encoding='utf-8') as txt_file:
            return [url.strip() for url in txt_file.readlines() if url.strip()]
