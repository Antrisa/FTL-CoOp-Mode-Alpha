#include "fleet_pixels.hpp"
#include <cassert>
#include <iostream>
int main(){
 std::vector<unsigned char> source(320*180*3);
 for(std::size_t i=0;i<source.size();++i)source[i]=static_cast<unsigned char>((i*79)%256);
 auto encoded=fleet::encodePixels(source);std::vector<unsigned char> decoded;
 assert(fleet::decodePixels(encoded,320,180,decoded)&&decoded==source);
 std::vector<unsigned char> solid(320*180*3,120);auto compressed=fleet::encodePixels(solid);
 assert(compressed.size()<2000 && fleet::decodePixels(compressed,320,180,decoded) && decoded==solid);
 auto old=decoded;
 assert(!fleet::decodePixels("00000000",1,1,decoded));assert(decoded==old);
 assert(!fleet::decodePixels("zz000000",1,1,decoded));assert(!fleet::decodePixels("02000000",1,1,decoded));
 assert(!fleet::decodePixels("01000000",320,180,decoded));assert(!fleet::decodePixels(encoded,321,180,decoded));
 assert(!fleet::decodePixels(encoded.substr(1),320,180,decoded));
 std::cout<<"Pixel codec roundtrip/bounds/atomic rejection passed\n";
}
