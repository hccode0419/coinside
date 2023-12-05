######################################################################################################
#                                                                                                    #
#                                                                                                    #
#                                                                                                    #
#                            변동성 돌파전략과 이동평균선을 이용한 자동매매 프로그램                       # 
#                                                                                                    #
#                                                                                                    #      
#                                                                                                    #
######################################################################################################
import ccxt
import pandas as pd
import time
import math


# apiKey.txt 파일에서 binance에서 발급받은 apikey와 비밀번호 key 저장
with open("apiKey.txt") as f:
    lines = f.readlines()
    apiKey = lines[0].strip()
    secret = lines[1].strip()

binance = ccxt.binance(config={
    "apiKey" : apiKey,
    "secret" : secret,
    "enableRateLimit":True,
    "options":{"defaultType":"future"}
})

balance = binance.fetch_balance()
symbol = "ETH/USDT" # 이더리움

def dataFrame():
    # 데이터프레임 객체로 변환
    btcOHLCV = binance.fetch_ohlcv("ETH/USDT", timeframe="5m", limit=1000)
    df = pd.DataFrame(btcOHLCV, columns=["datetime", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["datetime"], unit="ms") + pd.Timedelta(hours=9)
    
    # 구매가능 수량
    amount = calAmount(USDTBalance, curPrice, 0.5) # 30% 
    
    # 이동평균선 설정
    df.set_index("datetime", inplace=True)
    df["100ma"] = df["close"].rolling(100).mean()
    df["200ma"] = df["close"].rolling(200).mean()
    df["12ma"] = df["close"].rolling(12).mean()
    df["12ma_3"] = df["close"].shift(3).rolling(12).mean()
    df["30ma"] = df["close"].rolling(30).mean()
    df["30ma_3"] = df["close"].shift(3).rolling(30).mean()
  

    # 현재 계좌에 있는 돈
    df["balance"] = USDTBalance

    # 거래 총액
    df["tradeAmount"] = tradeAmount
    
    # diffMa
    df["diffMa"] = df["30ma"].iloc[-1] - df["12ma"].iloc[-1]
    
    # preDiffMa
    df["preDiffMa"] = df["30ma_3"].iloc[-1] - df["12ma_3"].iloc[-1]
    return df, amount

# 변동성 돌판전략
def VolatilityBreakout(df):   
    preCandle = df.iloc[-2]
    curcandle = df.iloc[-1]
    preCandleHigh = preCandle["high"] # 전 봉의 고가
    preCandleLow = preCandle["low"] # 전 봉의 저가
    curCandleOpen = curcandle["open"] # 현재 봉의 시가
    target = (preCandleHigh - preCandleLow)*k # 고가 - 저가
    longTarget = curCandleOpen + target # 롱 타겟
    shortTarget = curCandleOpen - target # 숏 타겟
    
    return longTarget, shortTarget

# 코인 구매 수량 계산
def calAmount(USDTBalance, curPrice, portion = 0.1):
    USDTTrade = USDTBalance * portion # 전체 자본의 portion : 10%
    MTA = 100000 # Minimum Trade Amount : 해당 숫자는 코인마다 상이하므로 수정해야함 0.00001
    amount = math.floor((USDTTrade * MTA)/curPrice) / MTA 

    return amount

# 포지션 진입
def enterPosition(exchange, symbol, curPrice, target, amount, position):
    if target == 1:
        position["type"] = "long"
        position["amount"] = amount
        tradeAmount = curPrice * amount
        print("롱")
        exchange.create_limit_buy_order(symbol=symbol, amount=amount, price = curPrice)
    elif target== -1:
        position["type"] = "short"
        position["amount"] = amount
        tradeAmount = curPrice * amount
        print("숏")
        exchange.create_limit_sell_order(symbol=symbol, amount=amount, price = curPrice)
    else:
        print("매수안함")
    return tradeAmount

# 포지션 종료
def exitPosition(exchange, symbol, curPrice, position):
    amount = position["amount"]
    tradeAmount = curPrice * amount
    if position["type"] =="long":
        print("롱 포지션 종료")
        exchange.create_limit_sell_order(symbol=symbol, amount=amount, price = curPrice)
        position["type"] = None
    elif position["type"] == "short":
        print("숏 포지션 종료")
        exchange.create_limit_buy_order(symbol=symbol, amount=amount, price = curPrice)
        position["type"] = None
    return tradeAmount

# USDT 잔고 조회
USDTBalance = balance["total"]["USDT"]
# USDTBalance = 1000

# 거래총액
tradeAmount = 0
position = {
    "type":None,
    "amount":0
}
# leverage 설정
market = binance.market(symbol)
leverage = 2
resp = binance.fapiprivate_post_leverage({
    "symbol":market["id"], # "ETHUSDT"
    "leverage":leverage
})
k = 0.5

entryPrice = 0
while(1):
    # 현재가
    coin = binance.fetch_ticker(symbol)
    curPrice = coin["last"]

    # USDT 잔고 조회
    balance = binance.fetch_balance()
    USDTBalance = balance["total"]["USDT"]

    # 데이터프레임
    df, amount = dataFrame()
    
    # 목표가 갱신
    longTargetByVB, shortTargetByVB = VolatilityBreakout(df)

    # 시간 포맷 설정
    df.index = df.index.strftime('%Y-%m-%d %H:%M:%S')

    # 엑셀 파일 생성
    with pd.ExcelWriter("../test.xlsx", engine='openpyxl') as writer:
        # 데이터프레임을 엑셀에 쓰기
        df.to_excel(writer, sheet_name='Sheet1', index=True)
        # 'A' 열의 크기를 조정
        writer.sheets['Sheet1'].column_dimensions['A'].width = 30  # 원하는 크기로 조정
        writer.sheets['Sheet1'].column_dimensions['M'].width = 15
        

    if df["diffMa"].iloc[-1] < 0:
        df.loc[df.index[-1], "diffMa"] *= -1
        # df["diffMa"].iloc[-1] = df["diffMa"].iloc[-1] * -1 
    if df["preDiffMa"].iloc[-1] < 0:
        df.loc[df.index[-1], "preDiffMa"] *= -1
        # df["preDiffMa"].iloc[-1] = df["preDiffMa"].iloc[-1] * -1

    targetByDiffMa = df["preDiffMa"].iloc[-1] * 0.5

    # 엔트리 조건
    # VB && baseTarget && realTarget && position
    isLongTarget = (curPrice > longTargetByVB) & (df["200ma"].iloc[-1] < df["100ma"].iloc[-1]) & (df["30ma"].iloc[-1] < df["12ma"].iloc[-1]) & (targetByDiffMa < df["diffMa"].iloc[-1]) & (position["type"] == None)
    isShortTarget = (curPrice < shortTargetByVB) & (df["200ma"].iloc[-1] > df["100ma"].iloc[-1]) & (df["30ma"].iloc[-1] > df["12ma"].iloc[-1]) & (targetByDiffMa < df["diffMa"].iloc[-1]) & (position["type"] == None)
 
    # 스탑 프로핏 조건
    isLongEnd = ((entryPrice + entryPrice * 0.005 < curPrice) or (entryPrice - entryPrice * 0.005 > curPrice)) & (position["type"] == "long") 
    isShortEnd = ((entryPrice - entryPrice * 0.005 > curPrice) or (entryPrice + entryPrice * 0.005 < curPrice)) & (position["type"] == "short")

    # 시간 출력
    print("현재가 : ", curPrice)
    print("VB롱 타겟 가격 :", longTargetByVB)
    print("VB숏 타겟 가격 :", shortTargetByVB)
    print("롱 타겟 :", curPrice > longTargetByVB)
    print("숏 타겟 :", curPrice < shortTargetByVB)
    print("진입 가격 :", entryPrice)
    print(f"targetDiffMa : {targetByDiffMa},  difffMa : {df['diffMa'].iloc[-1]}", targetByDiffMa < df["diffMa"].iloc[-1])
    print("base 진입 조건(False : short / True : long) : ", df["200ma"].iloc[-1], df["100ma"].iloc[-1], (df["200ma"].iloc[-1] < df["100ma"].iloc[-1])) 
    print("serve 진입 조건(False : short / True : long): ", df["30ma"].iloc[-1], df["12ma"].iloc[-1], df["30ma"].iloc[-1] < df["12ma"].iloc[-1])
    if position["type"] == None:
        pass
    elif position["type"] == "long":
        print("익절 : {}, 손절 : {}".format(entryPrice + entryPrice * 0.005, entryPrice - entryPrice * 0.005))
    elif position["type"] == "short":
        print("익절 : {}, 손절 : {}".format(entryPrice - entryPrice * 0.005, entryPrice + entryPrice * 0.005))
    print("포지션 타입", position["type"])

    # Long 포지션 엔트리
    if isLongTarget:
        entryPrice = curPrice
        tradeAmount = enterPosition(binance, symbol, curPrice, 1, amount, position)
        # USDTBalance = USDTBalance - tradeAmount
        
    # Long 포지션 스탑 프로핏
    if isLongEnd:
        tradeAmount = exitPosition(binance, symbol, curPrice, position)
        # USDTBalance = USDTBalance + tradeAmount

    # short 포지션 엔트리
    if isShortTarget:
        entryPrice = curPrice
        tradeAmount = enterPosition(binance, symbol, curPrice, -1, amount, position)
        # USDTBalance = USDTBalance - tradeAmount
        
    # short 포지션 스탑 프로핏
    if isShortEnd:
        tradeAmount = exitPosition(binance, symbol, curPrice, position)
        # USDTBalance = USDTBalance + tradeAmount

    print("ㅡ"*20)
    time.sleep(1)
