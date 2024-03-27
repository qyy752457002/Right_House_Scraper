import ssl
import re

ssl._create_default_https_context = ssl._create_unverified_context


import json
import os
from collections import OrderedDict
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from scrapy import Spider, Request

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Image, Table, TableStyle, PageBreak, PageTemplate, Frame, Spacer
from reportlab.platypus import BaseDocTemplate
from slugify import slugify

class RightmoveSpider(Spider):
    name = 'rightmove_pdf'
    base_url = 'https://www.rightmove.co.uk/'
    start_urls = [base_url]

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    }

    current_time = datetime.now().strftime('%d%m%Y %H%M%S')

    custom_settings = {
        'CONCURRENT_REQUESTS': 5,
        'FEED_EXPORTERS': {'xlsx': 'scrapy_xlsx.XlsxItemExporter'},
        'FEEDS': {
            f'./rightmove_properties/output/RightMove Properties {current_time}.xlsx': {
                'format': 'xlsx',
                'fields': ['Address', 'Price PCM', 'Price PW', 'Property Type', 'Bedrooms', 'Bathrooms',
                           'Available Date',
                           'Furnish Type', 'Image 1', 'Image 2', 'Image 3', 'Image 4', 'Image 5', 'Image 6', 'Image 7',
                           'Image 8', 'Image 9', 'Image 10', 'Floor Plan']
            }
        }
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.property_urls = self.get_property_urls_from_file()

        self.styles = getSampleStyleSheet()
        self.custom_style_title = ParagraphStyle('CustomStyleTitle', parent=self.styles['Heading1'], fontSize=14,
                                                 spaceAfter=0)

        self.custom_style_content = ParagraphStyle('CustomStyleContent', parent=self.styles['Normal'], fontSize=10,
                                                   leading=12, spaceAfter=3, fontName='Helvetica')
        self.doc = None
        # self.pdf_folder_path = f'./rightmove_properties/output/PDF Files {self.current_time}'

        # self.pdf_folder_path = f"./rightmove_properties/output/Images"
        # os.makedirs(self.pdf_folder_path)

    def start_requests(self):
        for url in self.property_urls:
            yield Request(url=url, headers=self.headers)

    def parse(self, response, **kwargs):
        images, images_urls, floor_plan = self.get_images(response)

        item = OrderedDict()
        item['Address'] = response.css('[itemprop="streetAddress"] ::text').get('').strip()
        item['Price PCM'] = response.css('article div span:contains(" pcm")::text').get('').replace('pcm', '').strip()
        item['Price PW'] = response.css('article div:contains("pw")::text').get('').replace('pw', '').strip()
        item['Property Type'] = self.get_value_by_heading(response, 'PROPERTY TYPE')
        item['Bedrooms'] = self.get_value_by_heading(response, 'BEDROOMS')
        item['Bathrooms'] = self.get_value_by_heading(response, 'BATHROOMS')
        item['Available Date'] = self.get_value_by_heading(response, 'Let available date:', letting_details=True)
        item['Furnish Type'] = self.get_value_by_heading(response, 'Furnish type:', letting_details=True)
        item['image_urls'] = images_urls
        item['Floor Plan image url'] = floor_plan
        item['images'] = images
        # item.update(images)

        # self.make_pdf(item=item, response=response)

        yield item

    def get_value_by_heading(self, response, heading, letting_details=False):
        return response.css(f'dl:contains("{heading}") dd ::text').get('').strip().replace('Ã—',
                                                                                           '') if not letting_details else response.css(
            f'dt:contains("{heading}") + dd::text').get('').strip()

    def get_images(self, response):
        try:
            json_data = json.loads(
                response.css('script:contains("propertyData")::text').re_first(r'window.PAGE_MODEL = (.*)'))
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

        floor_plan = floor_plan_image or response.css('a[href*="plan"] img::attr(src)').get('').replace('_max_296x197',
                                                                                                        '')
        image_urls = property_images or response.css(
            'a[itemprop="photo"] [itemprop="contentUrl"]::attr(content)').getall()

        image_items = {f'Image {index}': '' for index in range(1, 11)}

        # return {f'Image {index + 1}': image_url for index, image_url in enumerate(image_urls)}
        image_items.update(
            {f'Image {index + 1}': f'=IMAGE("{image_url}")' for index, image_url in enumerate(image_urls)})
        image_items.update({'Floor Plan': f'=IMAGE("{floor_plan}")'})

        return image_items, image_urls, floor_plan

    def get_property_urls_from_file(self):
        with open('./rightmove_properties/input/property_urls.txt', mode='r', encoding='utf-8') as txt_file:
            return [url.strip() for url in txt_file.readlines() if url.strip()]

    def make_pdf(self, item, response):
        """This method make the pdf file of given content.
         it get some content from item and other value like letting and key features getting from response """

        bed_room = item.get('Bedrooms').replace('x', '')
        bath_room = item.get('Bathrooms').replace('x', '')
        price = item.get('Price PW')
        price_bed_bath_values = f'<font bgcolor="{HexColor("#A6F79B ")}">{price} </font> | {bed_room} Bedroom | {bath_room} Bathroom'
        address = item.get('Address', '')

        letting_details_headers = response.css('._2RnXSVJcWbWv4IpBC1Sng6 dt::text').getall()
        letting_details_value = response.css('._2RnXSVJcWbWv4IpBC1Sng6 dd::text').getall()

        letting_details = [f"{label}{value}" for label, value in zip(letting_details_headers, letting_details_value)]
        letting_details = self.get_bullet_points(letting_details).replace('\n', '<br/>')

        key_features = self.get_bullet_points(response.css('.lIhZ24u1NHMa5Y6gDH90A ::text').getall()).replace('\n',
                                                                                                              '<br/>')

        # build file with property address name
        self.build_pdf_file(address)

        # use this para setting to  text align center of price_bed_bath_values anf address
        custom_style_title = ParagraphStyle('CustomStyleTitle', parent=self.styles['Heading1'], fontSize=14,
                                            spaceAfter=0, alignment=TA_CENTER)

        # this list contain the content of pdf file
        content = [
            Paragraph(f'<br/><br/>{address.title()}', custom_style_title),
            Paragraph(f'{price_bed_bath_values}<br/>', custom_style_title),
            Paragraph(f'<br/>', self.custom_style_content),
            self.create_images_table(item),
            Paragraph(f'<br/>', self.custom_style_content),
            PageBreak()
        ]

        floor_plane_image_url = item.get('Floor Plan image url')

        if floor_plane_image_url:
            content.append(Paragraph(f'<br/><br/>', self.custom_style_title))
            content.append(self.add_floor_plan_image(item))
            content.append(PageBreak())

        property_id = ''.join(response.url.split('/')[-1:])
        custom_style_content = ParagraphStyle(
            'CustomStyleContent', parent=self.styles['Normal'], fontSize=10, textColor='black',
            spaceBefore=10, alignment=2, leading=10, rightIndent=40
        )

        content.append(Paragraph(f'<br/>{property_id}', custom_style_content))

        if letting_details:
            content.append(Paragraph(f'<br/><u>Letting Details</u>:', self.custom_style_title))
            content.append(Paragraph(f'{letting_details}', self.custom_style_content))

        if key_features:
            content.append(Paragraph(f'<br/><u>key Features:</u>', self.custom_style_title))
            content.append(Paragraph(f'{key_features}', self.custom_style_content))

        # self.doc.build(content)
            
        try:
            self.doc.build(content)
        except Exception as e:
            self.log(f'Error during PDF generation: {e}')

        self.log(f'Property {address} PDF file saved')

    def create_images_table(self, item):
        """this method create a table of property images 4 rows and 2 cols """
        image_list = []

        # New width and height after adjustment
        new_width = 3.5 * inch  # inches (increased width)
        new_height = 2 * inch  # inches (decreased height)
        images_urls = item.get('image_urls', [])

        for image_url in images_urls[:8]:
            if image_url:
                image = Image(image_url, width=new_width, height=new_height)  # Adjust width and height
                image_list.append(image)

        num_images = len(image_list)
        if num_images % 2 != 0:
            image_list.append(Spacer(new_width, new_height))  # Add a spacer if the number of images is odd

        # Create the image table with two columns and four rows
        rows = [image_list[i:i + 2] for i in range(0, len(image_list), 2)]
        image_table = Table(rows, colWidths=[new_width, new_width])  # Adjust column widths

        image_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 3, colors.white),  # Add border to all cells
        ]))

        return image_table

    def build_pdf_file(self, address):

        try:

            pdf_file = f'{self.pdf_folder_path}/{slugify(address)}.pdf'

            self.doc = BaseDocTemplate(pdf_file, title='Properties', pagesize=letter, leftMargin=20, topMargin=15,
                                    rightMargin=6, bottomMargin=6)

            frame = Frame(self.doc.leftMargin, self.doc.bottomMargin, self.doc.width, self.doc.height - 50)

            header_template = PageTemplate(frames=[frame], onPage=self.pdf_page_header)

            self.doc.addPageTemplates(header_template)

        except Exception as e:
            self.log(f'Error in build_pdf_file: {e}')

    def pdf_page_header(self, canvas, doc):
        logo_width = 0.75 * inch
        logo_height = 0.75 * inch  # Increase the height of the logo to 0.75 inch
        logo_x = doc.leftMargin
        logo_y = doc.height + doc.topMargin - logo_height

        canvas.drawImage("./rightmove_properties/input/logo.PNG", logo_x, logo_y, width=logo_width, height=logo_height)

        pickup_line_style = ParagraphStyle(
            'PickupLineStyle', parent=self.styles['Normal'], fontSize=10, textColor='black',
            spaceAfter=1, alignment=2, leading=7  # Adjust the leading value to reduce space between lines
        )

        listed_by = '''NIKO RELOCATION<br/>
                        nikoinlondon@outlook.com<br/>
                        Wechat: nikoinlondon <br/>
                        www.nikorelocation.co.uk
                      '''
        pickup_line_text = listed_by.replace('\n', '<br/>')
        pickup_line_paragraph = Paragraph(pickup_line_text, pickup_line_style)

        # Adjust vertical position to place the pickup line below the logo
        pickup_line_y = doc.height + doc.topMargin - logo_height - 0.2 * inch
        top_margin = 0.5 * inch
        pickup_line_paragraph.wrapOn(canvas, doc.width - logo_width - 10, doc.topMargin)
        pickup_line_paragraph.drawOn(canvas, doc.width - pickup_line_paragraph.width - 10, pickup_line_y)

    def add_floor_plan_image(self, item):
        image_list = []

        # New width and height after adjustment
        new_width = 7 * inch  # Full width of the page
        new_height = 8.3 * inch  # Full height of the page

        floor_plane_image_url = item.get('Floor Plan image url')

        if floor_plane_image_url:
            image = Image(floor_plane_image_url, width=new_width, height=new_height)  # Adjust width and height
            # image_list.append(image)
            image_list.append([image])

        # Create the image table with a single row and a single column containing the image
        image_table = Table(image_list, colWidths=new_width, rowHeights=new_height)

        image_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 3, colors.white),  # Add border to the cell
        ]))

        return image_table

    def get_bullet_points(self, item_list):
        """ This method add bullets in list items and convert into string"""
        bullet_points = "\n".join(f"• {item}" for item in item_list)

        return bullet_points


