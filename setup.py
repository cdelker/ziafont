import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name = 'ziafont',
    version = '0.3',
    description = 'Convert TTF/OTF font glyphs to SVG paths',
    author = 'Collin J. Delker',
    author_email = 'ziaplot@collindelker.com',
    url = 'https://ziafont.readthedocs.io/',
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        'Source': 'https://bitbucket.org/cdelker/ziafont',
    },
    python_requires='>=3.8',
    packages=setuptools.find_packages(),
    package_data = {'ziafont': ['py.typed']},
    zip_safe=False,
    keywords = ['font', 'truetype', 'opentype', 'svg'],
    install_requires=[],
    classifiers = [
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Intended Audience :: Education',
    'Intended Audience :: Science/Research',
    'Intended Audience :: End Users/Desktop',
    'Intended Audience :: Developers',
    ],
)
