#pragma once
#include <string>
#include <vector>
#include <cstdint>
namespace fleet {
inline std::string encodePixels(const std::vector<unsigned char>& rgb){
    static const char* hex="0123456789abcdef";std::string out;
    if(rgb.empty()||rgb.size()%3||rgb.size()>320*180*3)return out;
    for(std::size_t i=0;i<rgb.size();){
        unsigned int count=1;
        while(count<255 && i+(count+1)*3<=rgb.size() && rgb[i]==rgb[i+count*3] && rgb[i+1]==rgb[i+count*3+1] && rgb[i+2]==rgb[i+count*3+2])++count;
        unsigned char bytes[]={static_cast<unsigned char>(count),rgb[i],rgb[i+1],rgb[i+2]};
        for(auto b:bytes){out+=hex[b>>4];out+=hex[b&15];}i+=count*3;
    }return out;
}
inline bool decodePixels(const std::string& hex,int w,int h,std::vector<unsigned char>& rgb){
    if(w<1||w>320||h<1||h>180||hex.empty()||hex.size()%8||hex.size()>320*180*8)return false;
    auto digit=[](char c)->int {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;return -1;};
    std::vector<unsigned char> clean;clean.reserve(w*h*3);
    for(std::size_t i=0;i<hex.size();i+=8){
        unsigned char b[4];for(int j=0;j<4;++j){int a=digit(hex[i+j*2]),c=digit(hex[i+j*2+1]);if(a<0||c<0)return false;b[j]=static_cast<unsigned char>(a*16+c);}
        if(!b[0] || clean.size()+b[0]*3>static_cast<std::size_t>(w*h*3))return false;
        for(int j=0;j<b[0];++j){clean.push_back(b[1]);clean.push_back(b[2]);clean.push_back(b[3]);}
    }
    if(clean.size()!=static_cast<std::size_t>(w*h*3))return false;
    rgb.swap(clean);return true;
}
}
