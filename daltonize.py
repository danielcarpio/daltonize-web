#!/usr/bin/env python

"""
   Modified by Daniel Carpio <danielcarpioc@gmail.com>
   Written by Joerg Dietrich <astro@joergdietrich.com>. Copyright 2015
   Based on original code by Oliver Siemoneit. Copyright 2007
   This code is licensed under the GNU GPL version 2, see COPYING for details.
"""

from __future__ import print_function, division
import pickle
from collections import OrderedDict
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pkg_resources import parse_version
from tkinter import *
from PIL import ImageTk
from PIL import Image
import numpy as np
assert parse_version(np.__version__) >= parse_version('1.9.0'), \
    "numpy >= 1.9.0 is required for daltonize"
try:
    import matplotlib as mpl
    _NO_MPL = False
except ImportError:
    _NO_MPL = True


def transform_colorspace(img, mat):
    """Transform image to a different color space.

    Arguments:
    ----------
    img : array of shape (M, N, 3)
    mat : array of shape (3, 3)
        conversion matrix to different color space

    Returns:
    --------
    out : array of shape (M, N, 3)
    """
    # Fast element (=pixel) wise matrix multiplication
    return np.einsum("ij, ...j", mat, img)


def simulate(img, color_deficit="d"):
    """Simulate the effect of color blindness on an image.

    Arguments:
    ----------
    img : PIL.PngImagePlugin.PngImageFile, input image
    color_deficit : {"d", "p", "t"}, optional
        type of colorblindness, d for deuteronopia (default),
        p for protonapia,
        t for tritanopia

    Returns:
    --------
    sim_rgb : array of shape (M, N, 3)
        simulated image in RGB format
    """
    # Colorspace transformation matrices
    cb_matrices = {
        "d": np.array([[1, 0, 0], [0.494207, 0, 1.24827], [0, 0, 1]]),
        "p": np.array([[0, 2.02344, -2.52581], [0, 1, 0], [0, 0, 1]]),
        "t": np.array([[1, 0, 0], [0, 1, 0], [-0.395913, 0.801109, 0]]),
    }
    rgb2lms = np.array([[17.8824, 43.5161, 4.11935],
                        [3.45565, 27.1554, 3.86714],
                        [0.0299566, 0.184309, 1.46709]])
    # Precomputed inverse
    lms2rgb = np.array([[8.09444479e-02, -1.30504409e-01, 1.16721066e-01],
                        [-1.02485335e-02, 5.40193266e-02, -1.13614708e-01],
                        [-3.65296938e-04, -4.12161469e-03, 6.93511405e-01]])

    img = img.copy()
    img = img.convert('RGB')

    rgb = np.asarray(img, dtype=float)
    # first go from RBG to LMS space
    lms = transform_colorspace(rgb, rgb2lms)
    # Calculate image as seen by the color blind
    sim_lms = transform_colorspace(lms, cb_matrices[color_deficit])
    # Transform back to RBG
    sim_rgb = transform_colorspace(sim_lms, lms2rgb)
    return sim_rgb


def array_to_img(arr):
    """Convert a numpy array to a PIL image.

    Arguments:
    ----------
    arr : array of shape (M, N, 3)

    Returns:
    --------
    img : PIL.Image.Image
        RGB image created from array
    """
    # clip values to lie in the range [0, 255]
    arr = clip_array(arr)
    arr = arr.astype('uint8')
    img = Image.fromarray(arr, mode='RGB')
    return img


def clip_array(arr, min_value=0, max_value=255):
    """Ensure that all values in an array are between min and max values.

    Arguments:
    ----------
    arr : array_like
    min_value : float, optional
        default 0
    max_value : float, optional
        default 255

    Returns:
    --------
    arr : array_like
        clipped such that all values are min_value <= arr <= max_value
    """
    comp_arr = np.ones_like(arr)
    arr = np.maximum(comp_arr * min_value, arr)
    arr = np.minimum(comp_arr * max_value, arr)
    return arr


def get_child_colors(child, mpl_colors):
    """
    Recursively enter all colors of a matplotlib objects and its
    children into a dictionary.

    Arguments:
    ----------
    child : a matplotlib object
    mpl_colors : OrderedDict from collections

    Returns:
    --------
    mpl_colors : OrderedDict
    """
    mpl_colors[child] = OrderedDict()
    if hasattr(child, "get_color"):
        mpl_colors[child]['color'] = child.get_color()
    if hasattr(child, "get_facecolor"):
        mpl_colors[child]['fc'] = child.get_facecolor()
    if hasattr(child, "get_edgecolor"):
        mpl_colors[child]['ec'] = child.get_edgecolor()
    if hasattr(child, "get_markeredgecolor"):
        mpl_colors[child]['mec'] = child.get_markeredgecolor()
    if hasattr(child, "get_markerfacecolor"):
        mpl_colors[child]['mfc'] = child.get_markerfacecolor()
    if hasattr(child, "get_markerfacecoloralt"):
        mpl_colors[child]['mfcalt'] = child.get_markerfacecoloralt()
    if isinstance(child, mpl.image.AxesImage):
        mpl_colors[child]['cmap'] = child.get_cmap()
        img_properties = child.properties()
        try:
            img_arr = img_properties['array']
            if len(img_arr.shape) == 3:
                mpl_colors[child]['array'] = np.array(img_arr)
        except KeyError:
            pass
    if hasattr(child, "get_children"):
        grandchildren = child.get_children()
        for grandchild in grandchildren:
            mpl_colors = get_child_colors(grandchild, mpl_colors)
    return mpl_colors


def get_mpl_colors(fig):
    """
    Read all colors used in a matplotlib figure into an OrderedDict.

    Arguments:
    ----------
    fig : matplotlib.figure.Figure

    Returns:
    --------
    mpl_dict : OrderedDict from collections
    """
    mpl_colors = OrderedDict()
    children = fig.get_children()
    for child in children:
        mpl_colors = get_child_colors(child, mpl_colors)
    return mpl_colors


def get_key_colors(mpl_colors, rgb, alpha):
    """From an OrderedDict of colors of all figure object children
    recursively fill rgb and alpha channel information.

    Arguments:
    ----------
    mpl_colors : OrderedDict
        dictionary with all colors of all children, matplotlib instances are
        keys
    rgb : array of shape (M, 1, 3)
        line image holding RGB colors encountered so far.
    alpha : array of shape (M, 1)
        line image holding alpha values encountered so far.

    Returns:
    --------
    rgb : array of shape (M+n, 1, 3)
    alpha : array of shape (M+n, 1)
    """
    if _NO_MPL is True:
        raise ImportError("matplotlib not found, "
                          "can only deal with pixel images")
    cc = mpl.colors.ColorConverter()  # pylint: disable=invalid-name
    # Note that the order must match the insertion order in
    # get_child_colors()
    color_keys = ("color", "fc", "ec", "mec", "mfc", "mfcalt", "cmap", "array")
    for color_key in color_keys:
        try:
            color = mpl_colors[color_key]
            # skip unset colors, otherwise they are turned into black.
            if isinstance(color, str) and color == 'none':
                continue
            if isinstance(color, mpl.colors.LinearSegmentedColormap):
                rgba = color(np.arange(color.N))
            elif isinstance(color, np.ndarray) and color_key == "array":
                color = color.reshape(-1, 3) / 255
                a = np.zeros((color.shape[0], 1))  # pylint: disable=invalid-name
                rgba = np.hstack((color, a))
            else:
                rgba = cc.to_rgba_array(color)
            rgb = np.append(rgb, rgba[:, :3])
            alpha = np.append(alpha, rgba[:, 3])
        except KeyError:
            pass
        for key in mpl_colors.keys():
            if key in color_keys:
                continue
            rgb, alpha = get_key_colors(mpl_colors[key], rgb, alpha)
    return rgb, alpha


def arrays_from_dict(mpl_colors):
    """
    Create rgb and alpha arrays from color dictionary.

    Arguments:
    ----------
    mpl_colors : OrderedDict
        dictionary with all colors of all children, matplotlib instances are
        keys

    Returns:
    --------
    rgb : array of shape (M, 1, 3)
        RGB values of colors in a line image, M is the total number of
        non-unique colors
    alpha : array of shape (M, 1)
        Alpha channel values of all mpl instances
    """
    rgb = np.array([])
    alpha = np.array([])
    for key in mpl_colors.keys():
        rgb, alpha = get_key_colors(mpl_colors[key], rgb, alpha)
    m = rgb.size // 3  # pylint: disable=invalid-name
    rgb = rgb.reshape((m, 1, 3))
    return rgb, alpha


def _set_colors_from_array(instance, mpl_colors, rgba, i=0):
    """
    Set object instance colors to the modified ones in rgba.
    """
    cc = mpl.colors.ColorConverter()  # pylint: disable=invalid-name
    # Note that the order must match the insertion order in
    # get_child_colors()
    color_keys = ("color", "fc", "ec", "mec", "mfc", "mfcalt", "cmap", "array")
    for color_key in color_keys:
        try:
            color = mpl_colors[color_key]
            if isinstance(color, mpl.colors.LinearSegmentedColormap):
                j = color.N
            elif isinstance(color, np.ndarray) and color_key == "array":
                j = color.shape[0] * color.shape[1]
            else:
                # skip unset colors, otherwise they are turned into black.
                if isinstance(color, str) and color == 'none':
                    continue
                color_shape = cc.to_rgba_array(color).shape
                j = color_shape[0]
            target_color = rgba[i: i + j, :]
            if j == 1:
                target_color = target_color[0]
            i += j
            if color_key == "color":
                instance.set_color(target_color)
            elif color_key == "fc":
                instance.set_facecolor(target_color)
            elif color_key == "ec":
                instance.set_edgecolor(target_color)
            elif color_key == "mec":
                instance.set_markeredgecolor(target_color)
            elif color_key == "mfc":
                instance.set_markerfacecolor(target_color)
            elif color_key == "mfcalt":
                instance.set_markerfacecoloralt(target_color)
            elif color_key == "cmap":
                instance.set_cmap(
                    instance.cmap.from_list(instance.cmap.name+"_dlt",
                                            target_color))
            elif color_key == "array":
                target_color = (target_color.reshape((color.shape[0],
                                                      color.shape[1],
                                                      -1)))
                target_color = (target_color[:, :, :3] * 255).astype('uint8')
                instance.set_data(target_color)
        except KeyError:
            pass
    return i


def set_mpl_colors(mpl_colors, rgba):
    """
    Recursively set the colors in a color dictionary to new values in rgba.

    Arguments:
    ----------
    mpl_colors : OrderedDict
        dictionary with all colors of all children, matplotlib instances are
        keys

    rgba : array of shape (M, 1, 4) containing rgb, alpha channels
    """
    i = 0
    for key in mpl_colors.keys():
        i = _set_colors_from_array(key, mpl_colors[key], rgba, i)


def _prepare_for_transform(fig):
    """
    Gather color keys/info for mpl figure and arange them such that the image
    simulate() or daltonize() routines can be called on them.
    """
    mpl_colors = get_mpl_colors(fig)
    rgb, alpha = arrays_from_dict(mpl_colors)
    return rgb, alpha, mpl_colors


def _join_rgb_alpha(rgb, alpha):
    """
    Combine (m, n, 3) rgb and (m, n) alpha array into (m, n, 4) rgba.
    """
    rgb = clip_array(rgb, 0, 1)
    r, g, b = np.split(rgb, 3, 2)  # pylint: disable=invalid-name, unbalanced-tuple-unpacking
    rgba = np.concatenate((r, g, b, alpha.reshape(alpha.size, 1, 1)),
                          axis=2).reshape(-1, 4)
    return rgba


def simulate_mpl(fig, color_deficit='d', copy=False):
    """
    Simulate color blindness on a matplotlib figure.

    Arguments:
    ----------
    fig : matplotlib.figure.Figure
    color_deficit : {"d", "p", "t"}, optional
        type of colorblindness, d for deuteronopia (default),
        p for protonapia,
        t for tritanopia
    copy : bool, optional
        should simulation happen on a copy (True) or the original
        (False, default)

    Returns:
    --------
    fig : matplotlib.figure.Figure
    """
    if copy:
        # mpl.transforms cannot be copy.deepcopy()ed. Thus we resort
        # to pickling.
        pfig = pickle.dumps(fig)
        fig = pickle.loads(pfig)
    rgb, alpha, mpl_colors = _prepare_for_transform(fig)
    sim_rgb = simulate(array_to_img(rgb * 255), color_deficit) / 255
    rgba = _join_rgb_alpha(sim_rgb, alpha)
    set_mpl_colors(mpl_colors, rgba)
    fig.canvas.draw()
    return fig

def takeScreenshot(url):
    """
    This function check which browser you have installed (currently only check Chromium and
    Firefox), open it with the given url and take a screenshot named original.png
    
    Arguments:
    ----------
    url : url of the website you want to take a screenshot

    Returns:
    --------
    Nothing
    """
    if Path("/usr/bin/chromium").is_file():
        driverpath = './drivers/chromedriver'
        windowSize = "1366,768"
        chromePath = '/usr/bin/chromium'
        chrome_options = Options()
        chrome_options.add_argument("--headless")  
        chrome_options.add_argument("--window-size=%s" % windowSize)
        chrome_options.binary_location = chromePath

        driver = webdriver.Chrome(executable_path=driverpath, options=chrome_options)
        driver.get(url)
        driver.save_screenshot('original.png')
        driver.quit()
    elif Path("/usr/bin/firefox").is_file():
        driver = webdriver.Firefox(executable_path="./drivers/geckodriver")
        driver.get(url)
        driver.save_screenshot('original.png')
        driver.quit()

    
if __name__ == '__main__':
    def buttonP():
        website = inpFe.get()
        takeScreenshot(website)
        for tipo in ["d", "p", "t"]:
            orig_img = Image.open("original.png")
            simul_rgb = simulate(orig_img, tipo)
            simul_img = array_to_img(simul_rgb)
            if tipo == "d":
                simul_img.save("deuteranopia.png")
            elif tipo == "p":
                simul_img.save("protanopia.png")
            else:
                simul_img.save("tritanopia.png")


        w1 = Toplevel(top)
        w1.title("Original")
        img1 = ImageTk.PhotoImage(Image.open("original.png"))
        panel1 = Label(w1, image=img1)
        panel1.image = img1
        panel1.pack(side=LEFT, fill="both", expand="yes")

        w2 = Toplevel(top)
        w2.title("Protanopia")
        img2 = ImageTk.PhotoImage(Image.open("protanopia.png"))
        panel2 = Label(w2, image=img2)
        panel2.image = img2
        panel2.pack(side=LEFT, fill="both", expand="yes")

        w3 = Toplevel(top)
        w3.title("Deuteranopia")
        img3 = ImageTk.PhotoImage(Image.open("deuteranopia.png"))
        panel3 = Label(w3, image=img3)
        panel3.image = img3
        panel3.pack(side=LEFT, fill="both", expand="yes")

        w4 = Toplevel(top)
        w4.title("Tritanopia")
        img4 = ImageTk.PhotoImage(Image.open("tritanopia.png"))
        panel4 = Label(w4, image=img4)
        panel4.image = img4
        panel4.pack(side=LEFT, fill="both", expand="yes")
        
    top = Tk()
    top.title("Daltonize-web")
    fraFe = Frame(top)
    fraFe.pack()
    etiFe = Label(fraFe, text='URL: ')
    etiFe.pack(side=LEFT)
    inpFe = Entry(fraFe)
    inpFe.pack(side=LEFT)
    busBu = Button(fraFe, text='Buscar', command=buttonP)
    busBu.pack(side=RIGHT)
    
    top.mainloop()
    
