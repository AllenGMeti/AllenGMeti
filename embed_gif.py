"""
Embed an animated GIF into light_mode.svg and dark_mode.svg.

Usage:  python embed_gif.py my_anime.gif [focus]
        focus = 0.0 (left) .. 1.0 (right): where to centre the crop on a wide GIF (default 0.5)

- Crops/resizes every frame to fill the 355x500 slot on the left of the card
- Keeps the animation timing
- Writes the GIF into both SVGs as a base64 data URI (the only way an <img>-loaded
  SVG on GitHub can show an image), replacing whatever sits between the
  GIF_SLOT markers, so you can re-run it any time to swap the GIF.
"""
import base64
import io
import re
import sys

from PIL import Image, ImageSequence

W, H = 355, 500          # size of the slot on the card
ENC = 0.5                # GIF is encoded at half size and scaled up by the SVG (much smaller file)
MAX_FRAMES = 24          # longer GIFs get every Nth frame dropped (timing is kept)
COLORS = 64
MAX_BYTES = 1_500_000    # keep the SVG comfortably small for GitHub's image proxy


def build_gif(path, focus_x=0.5):
    src = Image.open(path)
    raw = [(f.convert('RGB'), f.info.get('duration', 50)) for f in ImageSequence.Iterator(src)]
    step = max(1, -(-len(raw) // MAX_FRAMES))
    frames, durations = [], []
    for i in range(0, len(raw), step):
        f = raw[i][0]
        durations.append(sum(d for _, d in raw[i:i + step]))
        # crop a W:H window (full height unless the image is too narrow), horizontally around focus_x
        cw = min(f.width, round(f.height * W / H))
        ch = min(f.height, round(f.width * H / W))
        left = min(max(round(focus_x * f.width - cw / 2), 0), f.width - cw)
        top = (f.height - ch) // 2
        f = f.crop((left, top, left + cw, top + ch)).resize((round(W * ENC), round(H * ENC)), Image.LANCZOS)
        frames.append(f.convert('P', palette=Image.ADAPTIVE, colors=COLORS, dither=Image.NONE))
    buf = io.BytesIO()
    frames[0].save(buf, format='GIF', save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)
    return buf.getvalue(), len(frames)


def embed(svg_path, data_uri):
    with open(svg_path, encoding='utf-8', newline='') as fh:
        s = fh.read()
    nl = '\r\n' if '\r\n' in s else '\n'
    block = ('<!--GIF_SLOT_START-->' + nl +
             f'<image x="15" y="15" width="{W}" height="500" clip-path="url(#gif_clip)" '
             f'preserveAspectRatio="xMidYMid slice" href="{data_uri}"/>' + nl +
             '<!--GIF_SLOT_END-->')
    s, n = re.subn(r'<!--GIF_SLOT_START-->.*?<!--GIF_SLOT_END-->', lambda m: block, s, flags=re.S)
    if n != 1:
        sys.exit(f'{svg_path}: GIF slot markers not found')
    with open(svg_path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        sys.exit('usage: python embed_gif.py your.gif [focus 0..1]')
    data, n = build_gif(sys.argv[1], float(sys.argv[2]) if len(sys.argv) == 3 else 0.5)
    print(f'{n} frames, {len(data) / 1024:.0f} KB after resize')
    if len(data) > MAX_BYTES:
        print('WARNING: over 1.5 MB - GitHub may refuse to load it. Use a shorter/smaller GIF.')
    uri = 'data:image/gif;base64,' + base64.b64encode(data).decode()
    for svg in ('light_mode.svg', 'dark_mode.svg'):
        embed(svg, uri)
        print('updated', svg)
