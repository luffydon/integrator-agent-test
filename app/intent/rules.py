from __future__ import annotations
from typing import Tuple, Dict
LEX={'en':{'food':['food','eat','restaurant','menu','delivery','order'],'real_estate':['rent','apartment','flat','house','lease','real estate'],'transportation':['taxi','ride','bus','train','airport','uber'],'business':['service','company','invoice','payment','booking','categories']},'ru':{'food':['еда','поесть','ресторан','меню','доставка','заказать'],'real_estate':['аренда','квартира','дом','жильё','снять'],'transportation':['такси','поездка','автобус','поезд','аэропорт'],'business':['услуга','компания','счёт','оплата','бронь','категории']},'vi':{'food':['đồ ăn','ăn','nhà hàng','thực đơn','giao hàng','đặt món'],'real_estate':['thuê','căn hộ','nhà','bất động sản'],'transportation':['taxi','xe buýt','tàu','sân bay'],'business':['dịch vụ','công ty','hóa đơn','thanh toán','đặt chỗ','danh mục']},'de':{'food':['essen','restaurant','speisekarte','lieferung','bestellen'],'real_estate':['mieten','wohnung','haus','immobilie'],'transportation':['taxi','bus','zug','flughafen'],'business':['service','firma','rechnung','zahlung','buchung','kategorien']},'ko':{'food':['음식','먹다','식당','메뉴','배달','주문'],'real_estate':['임대','아파트','집','부동산'],'transportation':['택시','버스','기차','공항'],'business':['서비스','회사','청구서','결제','예약','카테고리']},}
def match_rules(text:str, lang:str)->Tuple[str,float,Dict]:
    t=(text or '').lower(); bag=LEX.get(lang, LEX['en']); best,conf='unknown',0.0
    for intent,words in bag.items():
        hits=sum(1 for w in words if w in t)
        if hits:
            c=min(0.5+0.1*hits,0.95)
            if c>conf: conf, best=c, intent
    return best, conf, {}
