# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from datetime import datetime
from itemadapter import ItemAdapter
from urllib import request
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image
import os

class RightmovePropertiesPipeline:

    def process_item(self, item, spider):

        global id

        # 获取 item中的图片地址
        image_urls = item["image_urls"]
        # 获取 item中的图片名称
        image_names = list(item["images"].keys())

        # 创建 images 文件夹 路径
        file_path = os.path.join('.', 'rightmove_properties', 'output', f'PDF Files {datetime.now().strftime("%d%m%Y %H%M%S")}')
        os.makedirs(file_path, exist_ok=True)

        for url, img_name in zip(item["image_urls"], item["images"].keys()):
            # 提取URL中的文件名，并为文件添加.jpeg扩展名
            filename = os.path.basename(url)
            if not filename.endswith(('.jpeg', '.jpg', '.png')):
                filename += '.jpeg'  # 假设图片是JPEG格式

            # 下载图片并保存
            full_file_path = os.path.join(file_path, img_name + '_' + filename)
            request.urlretrieve(url, full_file_path)
            print(f'Downloaded {url} to {full_file_path}')

        self.images_to_pdf(file_path, f'{file_path}.pdf')

        return item
    
    def images_to_pdf(self, images_folder, output_pdf):
        """
        将文件夹中的所有图片整合到一个PDF文件中
        """
        c = canvas.Canvas(output_pdf, pagesize=letter)
        width, height = letter  # 可以根据需要调整页面大小

        for filename in os.listdir(images_folder):
            if filename.endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(images_folder, filename)
                # 使用Pillow来确定图片的尺寸
                with Image.open(filepath) as img:
                    img_width, img_height = img.size
                    # 调整图片大小以适应页面
                    aspect = img_height / float(img_width)
                    new_width = width
                    new_height = new_width * aspect
                    # 确保图片不会超出页面边界
                    if new_height > height:
                        new_height = height
                        new_width = new_height / aspect
                    # 添加图片到PDF
                    x = (width - new_width) / 2
                    y = (height - new_height) / 2
                    c.drawImage(filepath, x, y, width=new_width, height=new_height)
                c.showPage()
        c.save()

