#!/usr/bin/env python3
"""Generate a small Open Images catalog for the LucYago Spelling GitHub Pages game."""
import csv
import io
import json
import os
import random
import threading
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
TARGET = int(os.environ.get('CATALOG_SIZE', '240'))
CLASSES = 'https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv'
LABELS = 'https://storage.googleapis.com/openimages/v5/validation-annotations-human-imagelabels-boxable.csv'
META = 'https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv'
WORDS = {'Cat':'gato','Dog':'perro','Horse':'caballo','Bird':'pájaro','Elephant':'elefante','Giraffe':'jirafa','Zebra':'cebra','Lion':'león','Tiger':'tigre','Bear':'oso','Sheep':'oveja','Cow':'vaca','Goat':'cabra','Pig':'cerdo','Chicken':'gallina','Duck':'pato','Fish':'pez','Shark':'tiburón','Dolphin':'delfín','Butterfly':'mariposa','Bee':'abeja','Spider':'araña','Snake':'serpiente','Turtle':'tortuga','Rabbit':'conejo','Squirrel':'ardilla','Frog':'rana','Monkey':'mono','Panda':'panda','Owl':'búho','Penguin':'pingüino','Fox':'zorro','Deer':'ciervo','Camel':'camello','Crocodile':'cocodrilo','Parrot':'loro','Eagle':'águila','Whale':'ballena','Crab':'cangrejo','Octopus':'pulpo','Snail':'caracol','Ant':'hormiga','Ladybug':'mariquita','Bicycle':'bicicleta','Car':'coche','Bus':'autobús','Train':'tren','Airplane':'avión','Boat':'barco','Motorcycle':'moto','Truck':'camión','Helicopter':'helicóptero','Apple':'manzana','Banana':'plátano','Orange':'naranja','Strawberry':'fresa','Pizza':'pizza','Cake':'pastel','Ice cream':'helado','Sandwich':'sándwich','Bread':'pan','Cheese':'queso','Hamburger':'hamburguesa','Egg':'huevo','Carrot':'zanahoria','Tomato':'tomate','Potato':'patata','Broccoli':'brócoli','Pineapple':'piña','Watermelon':'sandía','Grape':'uva','Lemon':'limón','Pear':'pera','Mushroom':'seta','Flower':'flor','Tree':'árbol','Sunflower':'girasol','Rose':'rosa','House':'casa','Castle':'castillo','Bridge':'puente','Tower':'torre','Clock':'reloj','Book':'libro','Pencil':'lápiz','Laptop':'portátil','Mobile phone':'móvil','Camera':'cámara','Guitar':'guitarra','Piano':'piano','Drum':'tambor','Violin':'violín','Ball':'pelota','Skateboard':'monopatín','Umbrella':'paraguas','Backpack':'mochila','Hat':'sombrero','Shoe':'zapato','Glasses':'gafas','Chair':'silla','Table':'mesa','Bed':'cama','Couch':'sofá','Toilet':'váter','Sink':'lavabo','Bathtub':'bañera','Refrigerator':'nevera','Television':'televisión','Bottle':'botella','Cup':'taza','Spoon':'cuchara','Fork':'tenedor','Toothbrush':'cepillo de dientes'}

def rows(url):
    print('Reading', url, flush=True)
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=100) as resp:
        yield from csv.DictReader(io.TextIOWrapper(resp, encoding='utf-8-sig', newline=''))

def value(row, *names):
    lower = {k.lower().replace('_',''):v for k,v in row.items() if k}
    for name in names:
        v = lower.get(name.lower().replace('_',''))
        if v: return v
    return ''

def allowed_license(url):
    return 'creativecommons.org/licenses/by/' in url.lower() or 'creativecommons.org/licenses/by-sa/' in url.lower()

def valid_url(url):
    return url.startswith(('https://','http://'))

classes = {value(r,'LabelName'):WORDS[value(r,'DisplayName')] for r in rows(CLASSES) if value(r,'DisplayName') in WORDS}
print('Recognized classes:', len(classes), flush=True)
if len(classes)<15: raise RuntimeError('No se reconocen suficientes clases; revisar CSV oficial')
labels=defaultdict(set)
for r in rows(LABELS):
    if value(r,'Confidence')!='1': continue
    name=classes.get(value(r,'LabelName'))
    if name: labels[value(r,'ImageID')].add(name)
print('Labeled images:', len(labels), flush=True)

candidates=defaultdict(list)
rejected=Counter()
for r in rows(META):
    tags=labels.get(value(r,'ImageID'))
    if not tags or len(tags)!=1:
        rejected['sin etiqueta única']+=1
        continue
    license_url=value(r,'License')
    if not allowed_license(license_url):
        rejected['licencia no admitida']+=1
        continue
    urls=[value(r,'Thumbnail300KURL'),value(r,'OriginalURL')]
    urls=list(dict.fromkeys(u for u in urls if valid_url(u)))
    if not urls:
        rejected['sin URL HTTP/HTTPS']+=1
        continue
    name=next(iter(tags))
    candidates[name].append({'id':value(r,'ImageID'),'name':name,'urls':urls,'license':license_url,'credit':value(r,'Author'),'source':value(r,'OriginalLandingURL')})
print('Available categories:',len(candidates),'candidate images:',sum(map(len,candidates.values())),flush=True)
print('Metadata filtered:',dict(rejected),flush=True)
if len(candidates)<6:
    raise RuntimeError('Menos de seis categorías disponibles. Revisar filtros de metadatos y licencias.')

random.seed(20261019)
for entries in candidates.values(): random.shuffle(entries)
# Limit downloads while sampling fairly across categories.
selected=[]
limit=max(TARGET*8, 1200)
while len(selected)<limit and any(candidates.values()):
    for name in sorted(candidates):
        if candidates[name]: selected.append(candidates[name].pop())
        if len(selected)>=limit: break

outdir=ROOT/'images'
outdir.mkdir(exist_ok=True)
lock=threading.Lock()
errors=Counter()

def download(item):
    last_error='enlace no accesible'
    for url in item['urls']:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8'})
            with urllib.request.urlopen(req,timeout=12) as resp:
                content_length=resp.headers.get('Content-Length')
                if content_length and int(content_length)>12_000_000:
                    last_error='archivo demasiado grande';continue
                raw=resp.read(12_000_001)
            if len(raw)>12_000_000:
                last_error='archivo demasiado grande';continue
            with Image.open(io.BytesIO(raw)) as im:
                im=ImageOps.exif_transpose(im).convert('RGB')
                if min(im.size)<180:
                    last_error='imagen demasiado pequeña';continue
                im.thumbnail((800,600))
                target=outdir/(item['id']+'.jpg')
                im.save(target,'JPEG',quality=76,optimize=True)
            return {k:item[k] for k in ('id','name','license','credit','source')}|{'url':'images/'+item['id']+'.jpg'}
        except Exception as exc:
            last_error=type(exc).__name__
    with lock: errors[last_error]+=1
    return None

results=[]
with ThreadPoolExecutor(max_workers=8) as executor:
    for f in as_completed([executor.submit(download,item) for item in selected]):
        item=f.result()
        if item:
            results.append(item)
            if len(results)%25==0:print('Downloaded',len(results),flush=True)
print('Successful downloads:',len(results),'of',len(selected),flush=True)
print('Download failure reasons:',dict(errors),flush=True)

random.shuffle(results)
byname=defaultdict(list)
for item in results:byname[item['name']].append(item)
final=[]
while len(final)<TARGET and any(byname.values()):
    for name in sorted(byname):
        if byname[name]:final.append(byname[name].pop())
        if len(final)>=TARGET:break

if len(final)<6 or len({x['name'] for x in final})<6:
    raise RuntimeError(f'Solo se descargaron {len(final)} fotos en {len({x["name"] for x in final})} categorías. Revisa los motivos de descarga anteriores.')
if len(final)<TARGET:
    print(f'WARNING: Catálogo parcial: {len(final)} de {TARGET} fotos solicitadas.',flush=True)

keep={x['id']+'.jpg' for x in final}
for path in outdir.glob('*.jpg'):
    if path.name not in keep:path.unlink()
(ROOT/'openimages-catalog.json').write_text(json.dumps({'version':1,'source':'Open Images validation, human-positive labels','count':len(final),'images':final},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print('Saved',len(final),'images in',len({x['name'] for x in final}),'categories',flush=True)
