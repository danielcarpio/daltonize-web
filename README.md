# Daltonize-web

Daltonize-web takes a capture of a website and simulates the three 
types of dichromatic color blindness and images and matplotlib 
figures. Generalizing and omitting a lot of details these types are:

* Deuteranopia: green weakness
* Protanopia: red weakness
* Tritanopia: blue weakness (extremely rare)

## Installation

git clone git@github.com:danielcarpio/daltonize-web.git

Used libraries:

* numpy
* selenium
* matplotlib

Currently, only works with Chromium and Firefox, so you have to install at 
least one of them

This software only works on Linux


## Usage

As a command line tool:

```
$ daltonize.py

and follow the steps.


## Credits

Based on the work by Jörg Dietrich, research scientist at the 
University Observatory Munich. His work can be found in:

https://github.com/joergdietrich/daltonize

Based on the work and original matlab code by Onur Fidaner, Poliang
Lin, Nevran Ozguven. This can be found in 'doc/'.

Based on original Python code by Oliver Siemoneit.

Further information on color blindness and daltonization is available
at many web resources, including http://www.daltonize.org/

Color blind friendly color maps can be found at
http://colorbrewer2.org/ All of these are included in the python
matplotlib and seaborn plotting libraries.

## License

This code is released und the GNU GPL version 2. See COPYING for details.
