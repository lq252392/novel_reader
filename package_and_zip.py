import os
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path

def install_cx_freeze():
    """检查并安装cx_Freeze"""
    try:
        import cx_Freeze
        print("cx_Freeze 已安装，跳过安装步骤。")
        return True
    except ImportError:
        print("未检测到 cx_Freeze，开始安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cx_Freeze"])
            print("cx_Freeze 安装成功！")
            return True
        except subprocess.CalledProcessError:
            print("错误：cx_Freeze 安装失败！")
            return False

def clean_build_dir():
    """清理旧的构建目录"""
    build_dir = Path("build")
    if build_dir.exists():
        print("清理旧的构建目录...")
        shutil.rmtree(build_dir)
        print("旧的构建目录已清理。")
    else:
        print("未发现旧的构建目录。")

def build_app():
    """执行打包命令"""
    print("开始打包...")
    result = subprocess.run([sys.executable, "setup.py", "build"])
    return result.returncode == 0

def find_build_dir():
    """查找打包后的目录"""
    build_path = Path("build")
    if build_path.exists():
        for item in build_path.iterdir():
            if item.is_dir() and item.name.startswith("exe."):
                return item
    return None

def zip_directory(source_dir, output_filename):
    """压缩目录"""
    print(f"正在压缩 {source_dir} 到 {output_filename}...")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(source_dir.parent)  # 从父目录开始计算相对路径
                zipf.write(file_path, arcname)
    
    print(f"压缩成功！压缩文件位置：{output_filename}")

def main():
    print("=" * 50)
    print("小说阅读器打包并压缩脚本")
    print("=" * 50)
    
    # 检查并安装cx_Freeze
    if not install_cx_freeze():
        input("按任意键退出...")
        return
    
    # 清理旧的构建目录
    clean_build_dir()
    
    # 执行打包
    if build_app():
        print("\n" + "=" * 50)
        print("打包成功！")
        print("=" * 50)
        
        # 查找构建目录
        build_dir = find_build_dir()
        if build_dir:
            print(f"发现构建目录: {build_dir}")
            
            # 获取目录名
            dir_name = build_dir.name
            
            # 创建压缩文件名
            zip_filename = f"NovelReader-{dir_name}.zip"
            
            # 压缩目录
            zip_directory(build_dir, zip_filename)
            
            print("\n" + "=" * 50)
            print(f"所有操作完成！")
            print(f"压缩文件位置：{os.path.abspath(zip_filename)}")
            print("=" * 50)
        else:
            print("未找到构建目录！")
    else:
        print("\n打包失败，请检查错误信息。")
    
    input("\n按任意键退出...")

if __name__ == "__main__":
    main()
