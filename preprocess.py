import pandas as pd

def clean():
    try:
        df = pd.read_csv('garbage.csv', encoding='utf-8')
    except:
        df = pd.read_csv('garbage.csv', encoding='gbk')

    # 保留纯分类标签，排除混合值
    valid = {1, 2, 4, 8, 16}
    df = df[df['category'].isin(valid)]
    
    # 标签直接用原始数字
    df[['name', 'category']].to_csv('train_data.csv', index=False, header=['name', 'label'])
    print(f"✅ 清洗完成！可用训练样本: {len(df)} 条")
    print("分类规则：1=可回收垃圾, 2=有害垃圾, 4=湿垃圾, 8=干垃圾, 16=大件垃圾")

if __name__ == "__main__":
    clean()