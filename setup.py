from setuptools import setup, find_packages

setup(
    name='mkdocs-linkedart-plugin',
    version='0.4.0',
    description='A MkDocs plugin',
    long_description='',
    keywords='mkdocs',
    url='',
    author='Rob Sanderson',
    author_email='azaroth42@gmail.com',
    license='MIT',
    python_requires='>=3.5',
    install_requires=[
        'mkdocs>=1.0.4'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    packages=find_packages(),
    entry_points={
        'mkdocs.plugins': [
            'linkedart = mkdocs_linkedart_plugin.plugin:LinkedArtPlugin'
        ]
    }
)
