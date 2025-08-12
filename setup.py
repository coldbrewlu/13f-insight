from setuptools import setup, find_packages

setup(
    name="insight13f",  # 包的名字（安装时用）
    version="0.1.0",
    packages=find_packages(where="src"),  # 在 src 下找所有包
    package_dir={"": "src"},  # 告诉 pip 代码在 src 下
    install_requires=[
        "requests",
        "pandas",
        # 其他依赖...
    ],
)
