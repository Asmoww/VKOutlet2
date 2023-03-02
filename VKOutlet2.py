from time import perf_counter, sleep
import requests
import json
import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
import math
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

#in seconds
cooldown = 600

maxthreads = 5

outlet_api_url = "https://web-api.service.verkkokauppa.com/search?filter=category%3A25a&pageNo=0&pageSize=48&context=customer_returns_page"

allproducts_url = "https://web-api.service.verkkokauppa.com/search?pageNo=0&pageSize=48&sort=score%3Adesc&lang=fi&context=customer_returns_page"

webhook_url = "https://discord.com/api/webhooks/1079729392059678740/Sg6ldIaBSNvqHo3Baku3lqvfTlr-orTlvk0Wa3s3gIqGVI-UVO95nhxnz7fqKWgoaABi"

verkkokauppa_logo = "https://pbs.twimg.com/profile_images/1145562519039283200/pfRACtCr_400x400.png"

product_link = "https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/"

filename = 'products.json'

logger = logging.getLogger('discord_webhook.webhook').disabled = True

missingProducts = []

global pagenum
pagenum = 0
global maxpages 
maxpages = 0

def log(message):
    if message == "CLEAR":
        print('\033[1A', end='\x1b[2K')
    else:
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

def change_prices(changes, filename="products.json"):
    with open(filename, "r") as readfile:
         file_data = json.load(readfile)
    with open(filename,'w') as writefile:
        for change in changes:
            file_data[change['id']]['discountprice'] = change['price']
        writefile.seek(0)
        json.dump(file_data, writefile, indent = 2)

def get_discount(oldprice, newprice):
    return round((1-(newprice/oldprice))*100, 1)

def new_webhook(embeds):
    webhook = DiscordWebhook(url=webhook_url)
    webhook.rate_limit_retry = True
    for embed in embeds:
        webhook.add_embed(embed)
    webhook.execute()

def send_webhooks(embeds):
    log('Sending webhook messages... 0 out of '+str(len(embeds)))
    wsent = 0
    embedlist = []
    for embed in embeds:
        if(len(embedlist) == 10):
            new_webhook(embedlist)
            wsent+=10
            log('CLEAR')
            log('Sending webhook messages... '+str(wsent)+' out of '+str(len(embeds))
            )
            embedlist.clear()
        embedlist.append(embed)
    if len(embedlist) > 0:
        log('CLEAR')
        log('Sending webhook messages... '+str(len(embeds))+' out of '+str(len(embeds)))
        new_webhook(embedlist)
        wsent+=len(embedlist)
    log('CLEAR')

def load_page(link):
    global pagenum
    response = requests.get(link)
    pagenum+=1
    if not response.status_code == 200:
        log("ERROR["+str(response.status_code)+"] RETRIEVING INFO FROM API ON PAGE " + str(pagenum))
    return json.loads(response.text)

def update_progress():
    while True:
        global pagenum
        global maxpages
        if (pagenum+1)==maxpages:
            return
        log('CLEAR')
        log('Loading pages... '+str(pagenum+1)+' out of '+str(maxpages))
        sleep(0.1)

def cycle():

    cycle_start = perf_counter()
    api_retrieve_start = perf_counter()

    newProducts = []
    priceChanges = []
    removedProducts = []
    allPages = []
    pageLinks = []
    webhookMessages = []

    response = requests.get(allproducts_url)
    responseJson = json.loads(response.text)
    allPages.append(responseJson)
    productCount = responseJson['totalItems']

    pages = math.ceil(productCount/48)
    global maxpages 
    maxpages = pages
    global pagenum 
    pagenum = 0

    log("Running cycle for "+str(productCount)+" products.")

    log("Loading pages... 1 out of "+str(pages))

    for pagenumber in range(1, pages): 
        pageLinks.append(allproducts_url.replace("pageNo=0", "pageNo="+str(pagenumber)))
        
    with ThreadPoolExecutor(max_workers=maxthreads) as executor:
        t = threading.Thread(target=update_progress)
        t.start()
        allPages = executor.map(load_page, pageLinks)


    log('CLEAR')
    api_retrieve_stop = perf_counter()

    log("Retrieved info from API in "+str(round(api_retrieve_stop-api_retrieve_start,3))+" seconds.")

    product_check_start = perf_counter()

    with open(filename, "r") as readfile:
        try:
            file = json.load(readfile)
        except:
            init_file()
            file = json.load(readfile)
        ids = []
        for page in allPages:
            #print(page)
            for product in page['products']:
                id = str(product['customerReturnsInfo']['id'])
                ids.append(id)
                if(not id in file):
                    priceInfo = product['price']
                    outletInfo = product['customerReturnsInfo']
                    productdata = {
                        id:
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
                        productdata[id]['imageurl'] = product['images'][0]['960']
                    except:
                        productdata[id]['imageurl'] = verkkokauppa_logo
                    newProducts.append(productdata)
                elif file[id]['discountprice'] != product['customerReturnsInfo']['price_with_tax']:
                    pricechange = {
                        'id':id,
                        'price':product['customerReturnsInfo']['price_with_tax'],
                        'oldprice':file[id]['discountprice']
                    }
                    priceChanges.append(pricechange)
        for id in missingProducts:
            removedProducts.append(id)
        missingProducts.clear()
        for id in file.keys():
            if id not in ids and id not in removedProducts:
                missingProducts.append(id)
            elif id in ids and id in removedProducts:
                removedProducts.remove(id)

        product_check_stop = perf_counter()

        log("Checked for new products and changes in "+str(round(product_check_stop-product_check_start, 3))+" seconds.")

        changes_start = perf_counter()

        if(len(missingProducts)>0):
            log(str(len(missingProducts)) + " products are missing.")

        if(len(newProducts) > 0):
            log(str(len(newProducts)) + " products were added.")
            for newproduct in newProducts:
                id = list(newproduct.keys())[0]
                info = newproduct[id]
                embed = DiscordEmbed(title="New product added!", color=716802)
                embed.description = "["+info['name']+"]("+product_link+str(id)+")"
                embed.set_thumbnail(info['imageurl'])
                embed.set_footer(text="verkkokauppa.com/outlet • "+str(id), icon_url=verkkokauppa_logo)
                embed.add_embed_field(name='Price', value="~~"+str(info['originalprice'])+"€~~  **"+str(info['discountprice'])+"**€\n**"+str(get_discount(info['originalprice'], info['discountprice']))+"**% off")
                embed.add_embed_field(name='Condition & info', value="**"+info['condition']+"**\n"+info['info'])
                embed.set_timestamp()
                webhookMessages.append(embed)
            save_products(newProducts)

        if(len(priceChanges)>0):
            log(str(len(priceChanges)) + " prices were changed.")
            for pricechange in priceChanges:
                product = file[pricechange['id']]
                embed = DiscordEmbed(title="Price changed :chart_with_downwards_trend:", color=4359413)
                embed.description = "["+product['name']+"]("+product_link+str(pricechange['id'])+")"
                embed.set_thumbnail(product['imageurl'])
                embed.set_footer(text="verkkokauppa.com/outlet • "+str(pricechange['id']), icon_url=verkkokauppa_logo)
                embed.add_embed_field(name='Price', value="**"+str(product['discountprice'])+"**€ >> **"+str(pricechange['price'])+"**€")
                embed.add_embed_field(name='Discount', value="**"+str(get_discount(product['originalprice'],product['discountprice']))+"**% >> **"+str(get_discount(product['originalprice'],pricechange['price']))+"**%")
                embed.set_timestamp()
                webhookMessages.append(embed)
            change_prices(priceChanges)

        if(len(removedProducts)>0):
            log(str(len(removedProducts)) + " products were removed.")
            for removedproduct in removedProducts:
                product = file[removedproduct]
                embed = DiscordEmbed(title="Product removed.", color=11010819)
                embed.description = "["+product['name']+"]("+product_link+str(removedproduct)+")"
                embed.set_thumbnail(product['imageurl'])
                embed.set_footer(text="verkkokauppa.com/outlet • "+str(removedproduct), icon_url=verkkokauppa_logo)
                embed.add_embed_field(name='Price', value="~~"+str(product['originalprice'])+"€~~  **"+str(product['discountprice'])+"**€\n**"+str(get_discount(product['originalprice'], product['discountprice']))+"**% off")
                embed.add_embed_field(name='Condition & info', value="**"+product['condition']+"**\n"+product['info'])
                embed.set_timestamp()
                webhookMessages.append(embed)
            remove_products(removedProducts)

        changes_stop = perf_counter()

        if len(priceChanges) + len(removedProducts) + len(newProducts) > 0:
            log("Made changes in " +str(round(changes_stop-changes_start, 3))+" seconds.")

            webhook_start = perf_counter()
            send_webhooks(webhookMessages)
            webhook_stop = perf_counter()   
            log("Sent webhook messages in "+str(round(webhook_stop-webhook_start, 3))+" seconds.")

    cycle_stop = perf_counter()
    log("Completed cycle in "+str(round(cycle_stop-cycle_start,3))+" seconds.")

passedtime = cooldown
while True:
    if(passedtime == cooldown):
        passedtime = 0
        log('CLEAR')
        cycle()
        print("")
        log('New cycle in '+str(cooldown)+' seconds.')
    sleep(1)
    passedtime+=1
    log('CLEAR')
    log('New cycle in '+str(cooldown-passedtime)+' seconds.')
