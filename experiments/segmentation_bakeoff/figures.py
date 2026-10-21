"""Render source-linked comparison figures from saved, unmodified polygons."""
import argparse
from PIL import Image, ImageDraw, ImageFont
from .common import ROOT, OUT, SYSTEMS, read


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('key')
    ap.add_argument('--crop', type=int, nargs=4)
    args = ap.parse_args()
    book,scan=args.key.split('/')
    baseline=read(ROOT/f'data/segmentation_bakeoff/baseline/{book}/{scan}.json')
    image=Image.open(ROOT/baseline['image']['path']).convert('RGB')
    crop=args.crop or (0,0,image.width,image.height)
    source=image.crop(crop)
    panel_width=800
    factor=panel_width/source.width
    panel_height=round(source.height*factor)
    canvas=Image.new('RGB',(panel_width*4,panel_height+75),'white')
    font=ImageFont.load_default(size=20)
    small=ImageFont.load_default(size=14)
    for col,(name,title) in enumerate([('kraken','Kraken (lines)'),('surya','Surya (lines)'),('ppocr','PP-OCRv5 (lines)'),('ppdoclayout','PP-DocLayoutV3 (blocks)')]):
        path=OUT/name/book/f'{scan}.json'
        if not path.exists(): path=ROOT/'results/segmentation_bakeoff'/name/book/f'{scan}.json'
        record=baseline if name=='kraken' else read(path)
        units=record['regions'] if name=='ppdoclayout' else record['lines']
        view=source.resize((panel_width,panel_height))
        draw=ImageDraw.Draw(view,'RGBA')
        for i,u in enumerate(units):
            polygon=u.get('polygon') or u.get('boundary')
            if not polygon: continue
            points=[((x-crop[0])*factor,(y-crop[1])*factor) for x,y in polygon]
            color=(0,115,175,200) if name=='ppdoclayout' else (0,130,55,190)
            draw.polygon(points,outline=color,width=2)
            if name=='ppdoclayout':
                draw.text(points[0],str(i),font=small,fill=(220,0,30,255))
        canvas.paste(view,(col*panel_width,75))
        d=ImageDraw.Draw(canvas)
        d.text((col*panel_width+10,8),title,font=font,fill='black')
        d.text((col*panel_width+10,37),f'{args.key} | {len(units)} detections on full page',font=small,fill='black')
    dest=OUT/'figures'/f"{book}_{scan}{'_crop' if args.crop else ''}.jpg"
    dest.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(dest,quality=94)
    print(dest)


if __name__ == '__main__':
    main()
