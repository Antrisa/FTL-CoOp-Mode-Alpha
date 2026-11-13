"""Validate a bounded RLE frame captured from FTL's own framebuffer, not the desktop."""
import re
from shared_map import integer

def validate_frame(f):
    if type(f)is not dict or set(f)!=set(('guard','width','height','data')):raise ValueError('frame fields')
    guard=integer(f['guard'],0,2**32-1);w=integer(f['width'],1,320);h=integer(f['height'],1,180);data=f['data']
    if type(data)is not str or not data or len(data)>320*180*8 or len(data)%8 or not re.fullmatch('[0-9a-f]+',data):raise ValueError('frame encoding')
    raw=bytes.fromhex(data);counts=raw[::4]
    if 0 in counts or sum(counts)!=w*h:raise ValueError('frame pixels')
    return dict(guard=guard,width=w,height=h,data=data)

def parse_frame(line):
    fields=line.split('|')
    if len(fields)!=5 or fields[0]!='VIEW':raise ValueError('frame line')
    return validate_frame(dict(zip(('guard','width','height','data'),fields[1:])))

def frame_line(f):
    f=validate_frame(f)
    return f"VIEW|{f['guard']}|{f['width']}|{f['height']}|{f['data']}\n"

# Compress only the known frame payload on the LAN path. Native loopback stays
# simple ASCII. Bounded decompression prevents malformed peers allocating freely.
def pack_frame(frame):
    import zlib,base64
    f=validate_frame(frame)
    return dict(guard=f['guard'],width=f['width'],height=f['height'],z=base64.b64encode(zlib.compress(bytes.fromhex(f['data']),1)).decode('ascii'))

def unpack_frame(frame):
    import zlib,base64,binascii
    if type(frame)is not dict or set(frame)!=set(('guard','width','height','z')) or type(frame['z'])is not str or len(frame['z'])>400000:raise ValueError('compressed frame')
    try:
        compressed=base64.b64decode(frame['z'],validate=True)
        d=zlib.decompressobj();raw=d.decompress(compressed,320*180*4+1)
        if len(raw)>320*180*4 or not d.eof or d.unconsumed_tail or d.unused_data:raise ValueError('compressed bounds')
    except (zlib.error,binascii.Error) as exc:raise ValueError('compressed encoding') from exc
    return validate_frame(dict(guard=frame['guard'],width=frame['width'],height=frame['height'],data=raw.hex()))
