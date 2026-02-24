from setuptools import setup, find_packages
import os

# Leer el README
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Leer la versión
with open(os.path.join('dte_gdexpress', '__init__.py'), 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

setup(
    name='dte-gdexpress',
    version=version,
    author='KreaSoft',
    author_email='soporte@kreasoft.cl',
    description='Paquete Python/Django para Facturación Electrónica Chilena con GDExpress/DTEBox',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Kreasoft/dte_gdexpress',
    project_urls={
        'Bug Tracker': 'https://github.com/Kreasoft/dte_gdexpress/issues',
        'Documentation': 'https://github.com/Kreasoft/dte_gdexpress/wiki',
        'Source Code': 'https://github.com/Kreasoft/dte_gdexpress',
    },
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
        'Framework :: Django :: 4.1',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Operating System :: OS Independent',
        'Natural Language :: Spanish',
    ],
    python_requires='>=3.8',
    install_requires=[
        'Django>=3.2',
        'cryptography>=41.0.0',
        'lxml>=4.9.0',
        'requests>=2.31.0',
        'python-decouple>=3.8',
        'Pillow>=10.0.0',  # Para códigos de barras
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-django>=4.5.0',
            'black>=23.7.0',
            'flake8>=6.1.0',
            'mypy>=1.5.0',
        ],
        'docs': [
            'sphinx>=7.1.0',
            'sphinx-rtd-theme>=1.3.0',
        ],
    },
    include_package_data=True,
    package_data={
        'dte_gdexpress': [
            'templates/*.html',
            'static/*',
        ],
    },
    keywords=[
        'dte',
        'facturacion electronica',
        'chile',
        'sii',
        'gdexpress',
        'dtebox',
        'factura',
        'boleta',
        'guia despacho',
        'nota credito',
    ],
    license='MIT',
    zip_safe=False,
)
