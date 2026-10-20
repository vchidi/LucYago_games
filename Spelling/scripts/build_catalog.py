#!/usr/bin/env python3
"""Build a small, locally hosted Open Images photo catalog for GitHub Pages.
Only human-positive validation labels; store resized images locally for stable delivery.
"""
import csv, io, json, os, random, time, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
TARGET=int(os.environ.get('CATALOG_SIZE','240'))
CLASSES='https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv'
LABELS='https://storage.googleapis.com/openimages/v5/validation-annotations-human-imagelabels-boxable.csv'
META='https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv'
WORDS={'Cat':'gato','Dog':'perro','Horse':'caballo','Bird':'pájaro','Elephant':'elefante','Giraffe':'jirafa','Zebra':'cebra','Lion':'león','Tiger':'tigre','Bear':'oso','Sheep':'oveja','Cow':'vaca','Goat':'cabra','Pig':'cerdo','Chicken':'gallina','Duck':'pato','Fish':'pez','Shark':'tiburón','Dolphin':'delfín','Butterfly':'mariposa','Bee':'abeja','Spider':'araña','Snake':'serpiente','Turtle':'tortuga','Rabbit':'conejo','Squirrel':'ardilla','Frog':'rana','Monkey':'mono','Panda':'panda','Owl':'búho','Penguin':'pingüino','Fox':'zorro','Deer':'ciervo','Camel':'camello','Crocodile':'cocodrilo','Parrot':'loro','Eagle':'águila','Whale':'ballena','Crab':'cangrejo','Octopus':'pulpo','Snail':'caracol','Ant':'hormiga','Ladybug':'mariquita','Bicycle':'bicicleta','Car':'coche','Bus':'autobús','Train':'tren','Airplane':'avión','Boat':'barco','Motorcycle':'moto','Truck':'camión','Helicopter':'helicóptero','Apple':'manzana','Banana':'plátano','Orange':'naranja','Strawberry':'fresa','Pizza':'pizza','Cake':'pastel','Ice cream':'helado','Sandwich':'sándwich','Bread':'pan','Cheese':'queso','Hamburger':'hamburguesa','Egg':'huevo','Carrot':'zanahoria','Tomato':'tomate','Potato':'patata','Broccoli':'brócoli','Pineapple':'piña','Watermelon':'sandía','Grape':'uva','Lemon':'limón','Pear':'pera','Mushroom':'seta','Flower':'flor','Tree':'árbol','Sunflower':'girasol','Rose':'rosa','House':'casa','Castle':'castillo','Bridge':'puente','Tower':'torre','Clock':'reloj','Book':'libro','Pencil':'lápiz','Laptop':'portátil','Mobile phone':'móvil','Camera':'cámara','Guitar':'guitarra','Piano':'piano','Drum':'tambor','Violin':'violín','Ball':'pelota','Skateboard':'monopatín','Umbrella':'paraguas','Backpack':'mochila','Hat':'sombrero','Shoe':'zapato','Glasses':'gafas','Chair':'silla','Table':'mesa','Bed':'cama','Couch':'sofá','Toilet':'váter','Sink':'lavabo','Bathtub':'bañera','Refrigerator':'nevera','Television':'televisión','Bottle':'botella','Cup':'taza','Spoon':'cuchara','Fork':'tenedor','Toothbrush':'cepillo de dientes'}

def rows(url):
    print('Reading',url,flush=True)
    req=urllib.request.Request(url,headers={'User-Agent':'LucYagoCatalogBuilder/1.0'})
    with urllib.request.urlopen(req,timeout=100) as resp:
        wrapper=io.TextIOWrapper(resp,encoding='utf-8-sig',newline='')
        yield from csv.DictReader(wrapper)

def value(row,*names):
    lower={k.lower().replace('_',''):v for k,v in row.items() if k}
    for n in names:
        v=lower.get(n.lower().replace('_',''))
        if v:return v
    return ''

classes={value(r,'LabelName'):WORDS[value(r,'DisplayName')] for r in rows(CLASSES) if value(r,'DisplayName') in WORDS}
print('Recognized classes:',len(classes),flush=True)
assert len(classes)>15,'No classes found; verify official metadata URL and schema'
labels=defaultdict(set)
for r in rows(LABELS):
    if value(r,'Confidence')!='1':continue
    name=classes.get(value(r,'LabelName'))
    if name:labels[value(r,'ImageID')].add(name)
print('Labeled images:',len(labels),flush=True)

candidates=defaultdict(list)
for r in rows(META):
    image_id=value(r,'ImageID')
    tags=labels.get(image_id)
    if not tags or len(tags)!=1:continue
    license_url=value(r,'License')
    if 'creativecommons.org/licenses/by/' not in license_url:continue
    url=value(r,'OriginalURL','Thumbnail300KURL')
    if not url.startswith('https://'):continue
    name=next(iter(tags))
    candidates[name].append({'id':image_id,'name':name,'original_url':url,'license':license_url,'credit':value(r,'Author'),'source':value(r,'OriginalLandingURL')})
print('Available categories:',len(candidates),flush=True)
assert len(candidates)>=6,'Not enough image categories for six Guess choices'
random.seed(20261019)
for entries in candidates.values():random.shuffle(entries)
# Round-robin categories avoids oversampling cats/dogs.
selected=[]
while len(selected)<TARGET*5 and any(candidates.values()):
    for name in sorted(candidates):
        if candidates[name]:selected.append(candidates[name].pop())
        if len(selected)>=TARGET*5:break

outdir=ROOT/'images';outdir.mkdir(exist_ok=True)

def download(item):
    try:
        req=urllib.request.Request(item['original_url'],headers={'User-Agent':'Mozilla/5.0 (compatible; LucYago/1.0)'})
        with urllib.request.urlopen(req,timeout=16) as resp:
            if resp.headers.get('Content-Length') and int(resp.headers['Content-Length'])>12_000_000:return None
            raw=resp.read(12_000_001)
        if len(raw)>12_000_000:return None
        with Image.open(io.BytesIO(raw)) as im:
            im=ImageOps.exif_transpose(im).convert('RGB')
            if min(im.size)<200:return None
            im.thumbnail((800,600))
            target=outdir/(item['id']+'.jpg')
            im.save(target,'JPEG',quality=76,optimize=True)
        return {k:item[k] for k in ('id','name','license','credit','source')}|{'url':'images/'+item['id']+'.jpg'}
    except Exception:return None

results=[];counts=defaultdict(int)
with ThreadPoolExecutor(max_workers=10) as executor:
    pending={executor.submit(download,x):x for x in selected}
    for f in as_completed(pending):
        item=f.result()
        if item:
            results.append(item);counts[item['name']]+=1
            if len(results)%25==0:print('Downloaded',len(results),flush=True)
# Pick balanced 240 from successfully downloaded pool, remove surplus images.
random.shuffle(results)
byname=defaultdict(list)
for item in results:byname[item['name']].append(item)
final=[]
while len(final)<TARGET and any(byname.values()):
    for name in sorted(byname):
        if byname[name]:final.append(byname[name].pop())
        if len(final)>=TARGET:break
assert len(final)>=6 and len({x['name'] for x in final})>=6,'Not enough reachable, licensed photos'
keep={x['id']+'.jpg' for x in final}
for path in outdir.glob('*.jpg'):
    if path.name not in keep:path.unlink()
(ROOT/'openimages-catalog.json').write_text(json.dumps({'version':1,'source':'Open Images validation, human-positive labels','count':len(final),'images':final},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print('Saved',len(final),'images in',len({x['name'] for x in final}),'categories',flush=True)
