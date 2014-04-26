from setuptools import setup, find_packages


setup(
    name='spiral-swarm',
    description='easy local file transfer with curvecp',
    author='Aaron Gallagher',
    author_email='_@habnab.it',
    packages=find_packages(),
    install_requires=[
        'fish',
        'spiral',
    ],
    setup_requires=['vcversioner'],
    vcversioner={
        'version_module_paths': ['spiralswarm/_version.py'],
    },
    entry_points={
        'console_scripts': ['spiral-swarm = spiralswarm.application:main'],
    },
)
