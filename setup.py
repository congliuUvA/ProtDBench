from setuptools import find_packages, setup

setup(
    name="protdbench",
    version="0.1.2",
    description="ProtDBench: Benchmark Suite for De Novo Protein Binder Design",
    author="Cong Liu",
    author_email="c.liu4@uva.nl",
    url="https://github.com/congliuUvA/ProtDBench",
    license="Apache-2.0",
    python_requires=">=3.10",
    packages=find_packages(include=["protdbench", "protdbench.*"]),
)
