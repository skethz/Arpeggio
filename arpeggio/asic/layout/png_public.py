"""Re-encode a GUI dump as a metadata-free RGB PNG (no text chunks). usage: png_public.py <in.png> <out.png>"""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB')
im.save(sys.argv[2], format='PNG', optimize=False)
print('PNG_PUBLIC', im.size[0], im.size[1])
