from time import perf_counter
import requests
import json
import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
import math

#url of first page of specified category
outlet_api_url = "https://web-api.service.verkkokauppa.com/search?filter=category%3A25a&pageNo=0&pageSize=48&context=customer_returns_page"

allproducts_url = "https://web-api.service.verkkokauppa.com/search?pageNo=0&pageSize=48&sort=score%3Adesc&lang=fi&context=customer_returns_page"

webhook_url = "https://discord.com/api/webhooks/1079729392059678740/Sg6ldIaBSNvqHo3Baku3lqvfTlr-orTlvk0Wa3s3gIqGVI-UVO95nhxnz7fqKWgoaABi"

verkkokauppa_logo = "https://pbs.twimg.com/profile_images/1145562519039283200/pfRACtCr_400x400.png"

product_link = "https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/"

filename = 'products.json'

def log(message):
    print("["+datetime.datetime.now().strftime("%H:%M:%S")+"] "+message)

def init_file():
    with open(filename,'r+') as file:
        file_data = { }
        file.seek(0)
        json.dump(file_data, file, indent = 2)

def save_products(new_data, filename='products.json'):
    with open(filename,'r+') as file:
        file_data = json.load(file)
        for product in new_data:
            file_data.update(product)
        file.seek(0)
        json.dump(file_data, file, indent = 2)

def remove_products(products, filename='products.json'):
    with open(filename, "r") as readfile:
         file_data = json.load(readfile)
    with open(filename,'w') as writefile:
        for id in products:
            del file_data[str(id)]
        writefile.seek(0)
        json.dump(file_data, writefile, indent = 2)

def change_price(id, value, filename="products.json"):
    with open(filename, "r") as readfile:
         file_data = json.load(readfile)
    with open(filename,'w') as writefile:
        for i, outletid in enumerate(id):
            file_data[str(outletid)]["discountprice"]=value[i]
        writefile.seek(0)
        json.dump(file_data, writefile, indent = 2)

def get_discount(oldprice, newprice):
    return round((1-(newprice/oldprice))*100, 1)

def newproduct_webhook(name, link, oldprice, newprice, condition, info, outletid, image):
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="New product added!", color=716802)
    embed.description = "["+name+"]("+link+")"
    embed.set_thumbnail(image)
    embed.set_footer(text="verkkokauppa.com/outlet • "+str(outletid), icon_url=verkkokauppa_logo)
    embed.add_embed_field(name='Price', value="~~"+str(oldprice)+"€~~  **"+str(newprice)+"**€\n**"+str(get_discount(oldprice, newprice))+"**% off")
    embed.add_embed_field(name='Condition & info', value="**"+condition+"**\n"+info)
    embed.set_timestamp()
    webhook.add_embed(embed)
    webhook.execute()

api_retrieve_start = perf_counter()

productNum = 0
newProducts = []
allPages = []

response = requests.get(allproducts_url)
responseJson = json.loads(response.text)
allPages.append(responseJson)
productCount = responseJson['totalItems']

pages = math.ceil(productCount/48)

log("Retrieving info for "+str(productCount)+" products on "+str(pages)+" pages...")

for pagenum in range(1, pages): 
    next_page = allproducts_url.replace("pageNo=0", "pageNo="+str(pagenum))
    response = requests.get(next_page)
    allPages.append(json.loads(response.text))
    log(str(pagenum))
    if not response.status_code == 200:
        log("ERROR["+str(response.status_code)+"] RETRIEVING INFO FROM API ON PAGE " + str(pagenum))

api_retrieve_stop = perf_counter()

log("Retrieved info from API in "+str(round(api_retrieve_stop-api_retrieve_start,3))+" seconds.")

product_check_start = perf_counter()

for page in allPages:
    with open(filename, "r") as readfile:
        try:
            file = json.load(readfile)
        except:
            init_file()
            file = json.load(readfile)
        for product in page['products']:
            productNum += 1
            if(not str(product['customerReturnsInfo']['id']) in file):
                priceInfo = product['price']
                outletInfo = product['customerReturnsInfo']
                productdata = {
                    outletInfo['id']:
                        {
                            "name":outletInfo['product_name'],
                            "discountprice": outletInfo['price_with_tax'],
                            "originalprice": priceInfo['original'],
                            "condition": outletInfo['condition'],
                            "info": outletInfo['product_extra_info'],
                            "imageurl": "blank"
                        }
                }          
                try:
                    productdata['imageurl'] = product['images'][0]['960']
                except:
                    productdata['imageurl'] = verkkokauppa_logo
                newProducts.append(productdata)
                #log(str(productNum) +" "+ str(outletInfo['id']) +" new "+ str(outletInfo['price_with_tax']) +" original "+ str(priceInfo['original']))

product_check_stop = perf_counter()

log("Checked products in "+str(round(product_check_stop-product_check_start, 3))+" seconds.")

if(len(newProducts) > 0):
    log(str(len(newProducts)) + " new products were found.")
    save_start = perf_counter()
    save_products(newProducts)
    save_stop = perf_counter()
    log("Saved new products in " +str(round(save_stop-save_start, 3))+" seconds.")
    webhook_start = perf_counter()
    for product in newProducts:
        id = list(product.keys())[0]
        info = product[id]
        #newproduct_webhook(info['name'],product_link+str(id),info['originalprice'],info['discountprice'],info['condition'],info['info'],str(id),info['imageurl'])
    webhook_stop = perf_counter()   
    log("Sent webhook messages in "+str(round(webhook_stop-webhook_start, 3))+" seconds.")



