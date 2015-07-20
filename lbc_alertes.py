#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Envoi par email de nouvelles annonces Le Bon Coin, en fonction d'une page de résultats de recherche
"""

import urllib
import re
import os
import argparse
import ConfigParser
import smtplib
import json
from datetime import datetime, timedelta
from pyquery import PyQuery as pq
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

import codecs,sys
sys.stdout=codecs.getwriter('utf-8')(sys.stdout)

#####################################################################

parser = argparse.ArgumentParser(description='Création (ou mise à jour) d\'une base de données JSON pour une recherche Le Bon Coin')
parser.add_argument('config', metavar='fichier de configuration', help='Le fichier de configuration des alertes')
args = parser.parse_args()

config = ConfigParser.ConfigParser()
config.read(args.config)

result_url  = config.get('core', 'url')
json_file   = config.get('core', 'bd_file')

#####################################################################

def format_price(price):
    if price < 1000:
        return str(price) + u' €'
    else:
        return str(price/1000) + u' k€'

#####################################################################

if os.path.isfile(json_file) :
    input_json = open(json_file, 'r')
    annonces_db = json.load(input_json)
    input_json.close()
else:
    annonces_db = {}

new_annonces_id = []

regexp_id = re.compile(r"/([0-9]+)\.htm")
regexp_price = re.compile(r"[^0-9]")

today          = datetime.now()
yesterday      = today - timedelta(days=1)
today_date     = today.strftime('%d/%m/%Y')
yesterday_date = yesterday.strftime('%d/%m/%Y')

d = pq(url=result_url)

for annonce_bloc in d('.list-lbc > a'):

    annonce_data = {}

    ## titre
    title =  pq(annonce_bloc).attr('title')
    print title
    annonce_data['titre'] = title

    ## lien
    link =  pq(annonce_bloc).attr('href')
    print link
    annonce_data['lien'] = link

    ## date
    day,hour = pq(annonce_bloc).find('.date div')
    if day.text == "Aujourd'hui":
        day = today_date
    elif day.text == "Hier":
        day = yesterday_date
    else:
        day = day.text
    print day,hour.text
    annonce_data['jour'] = day
    annonce_data['heure'] = hour.text

    ## image
    image = pq(annonce_bloc).find('.image img').attr('src')
    print image
    annonce_data['image'] = image

    ## categorie
    categorie = pq(annonce_bloc).find('.category').text().strip()
    print categorie
    annonce_data['categorie'] = categorie

    ## placement
    placement = pq(annonce_bloc).find('.placement').text().split('/')
    placement = ' / '.join([p.strip() for p in placement])
    print placement
    annonce_data['emplacement'] = placement

    ## price
    price = pq(annonce_bloc).find('.price').text().strip()
    price = int(re.sub(regexp_price, '', price))
    print price
    annonce_data['prix'] = price

    ## hash
    match = regexp_id.search(link)
    if match:
        annonce_id = match.group(1)
        hash = annonce_id
    else:
        annonce_id = 0
        hash = 0
    annonce_data['id']   = annonce_id

    ## ajout de l'annonce dans la base
    if not hash in annonces_db:
        new_annonces_id.append(hash)
    else:
        # check price change
        old_price = annonces_db[hash]['prix']
        if old_price != price:
            new_annonces_id.append(hash)
            annonce_data['prix_ancien'] = old_price
        pass
    annonces_db[hash] = annonce_data

    print '--------------'


## sauvegarde de la base
output_json = open(json_file, 'wb')
json_str = json.dumps(annonces_db, indent=4, separators=(',', ': '), sort_keys=True)
output_json.write(json_str)
output_json.close()

print str(len(annonces_db)) + u" annonces."
print str(len(new_annonces_id)) + u" nouvelles annonces."
print u"Base de données exportée : "+json_file


## envoi de l'email
if ( len(new_annonces_id) > 0 ):

    annonces_list = ''
    annonce_template = Template("""\
        <li style="margin-bottom: 40px;">
            <a style="text-decoration: none; color: black;" href="$link" title="$title">
                <img style="float: left; margin-right: 10px;" src="$img" alt="$title" />
                <h3>$title</h3>
                <p>$price</p>
                <p>$date</p>
                <p style="clear: both;"></p>
            <a/>
        </li>
    """)

    for hash in new_annonces_id:
        annonce_data = annonces_db[hash]

        ## gestion de l'image
        if annonce_data['image'] is None:
            img = 'http://www.fillmurray.com/160/120'
        else:
            img = annonce_data['image']

        ## gestion du prix
        if 'prix_ancien' in annonce_data:
            price  = '<strong>NOUVEAU PRIX : ' + format_price(annonce_data['prix']) + u'</strong>'
            price += ' (ancien prix : ' + format_price(annonce_data['prix_ancien']) + u')'
        else:
            price = format_price(annonce_data['prix'])

        annonce_html = annonce_template.substitute(link=annonce_data['lien'],title=unicode(annonce_data['titre']),img=img,price=price,date=(annonce_data['jour'] + ' ' + annonce_data['heure']))
        annonces_list += annonce_html

    to_email   = config.get('email', 'to_email')
    from_email = config.get('email', 'from_email')
    username   = config.get('email', 'username')
    password   = config.get('email', 'password')
    server     = config.get('email', 'server')

    msg = MIMEMultipart('alternative')
    msg['From'] = from_email
    msg['To'] = to_email
    to_list = [email.strip() for email in to_email.split(',')]
    if config.has_option('email', 'cc'):
        msg['cc'] = config.get('email', 'cc')
        cc_list = [email.strip() for email in config.get('email', 'cc').split(',')]
        to_list += cc_list

    if config.has_option('email', 'subject_prefix'):
        msg['Subject'] = config.get('email', 'subject_prefix') + ' :: Alertes Le Bon Coin : nouvelle(s) annonce(s) !'
    else:
        msg['Subject'] = 'Alertes Le Bon Coin : nouvelle(s) annonce(s) !'

    html_template = Template(u"""\
    <html>
      <head></head>
      <body>
        <ul style="list-style-type: none;">
            $annonces_list
        </ul>
        <p>Lien de recherche correspondant à ces annonces : <a href="$lien_recherche">résultats Le Bon Coin</a></p>
        <p>Si vous ne souhaitez plus recevoir ces emails, allez vous faire foutre.</p>
      </body>
    </html>
    """)
    html = html_template.substitute(annonces_list=annonces_list, lien_recherche=result_url)
    part_html = MIMEText(html, 'html', 'utf-8')
    msg.attach(part_html)

    server = smtplib.SMTP(server)
    server.starttls()
    server.login(username,password)
    server.sendmail(msg['From'], to_list, msg.as_string())
    server.quit()

    print u"Email envoyé à : "+str(to_email)
else:
    print u"Pas d'email envoyé"