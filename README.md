# e-ORP

<picture>
 <source media="(prefers-color-scheme: dark)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/e-orp-dark-logo-240.png">
 <source media="(prefers-color-scheme: light)" srcset="https://github.com/dcurrie/e-ORP/blob/main/doc/e-orp-light-logo-240.png">
 <img alt="e-ORP" src="[e-ORP](https://github.com/dcurrie/e-ORP/blob/main/doc/e-orp-light-logo-240.png)">
</picture>

Optimal Retirement Planner

Inspired by the now unmaintained (and unavailable?) `i-ORP` by James Welch, this
is a Jupyter notebook version of that optimizer. It is far less capable, and 
still quite new.

## DISCLAIMER

This tool is freely offered for your enjoyment, but please be aware that:

1. It is new and undoubtedly has defects
2. I am not a financial planner 
3. I am not an expert in linear programming optimization

**Use at your own risk!**  

If you find what you believe is a defect in the code, please report it!

## Known Limitations and Quirks

- [ ] The `i-ORP` IRMAA feature is not implemented
- [ ] `e-ORP` assumes the OBBBA extra tax deduction of $6000 applies to anyone over 65 between the years 2025 through 2028, and does not phase out the deduction for AGIs above $150,000 (joint, $75,000 single)
- [ ] The `i-ORP` spending glide path is not implemented
- [ ] There are undoubtedly several other missing `i-ORP` features, but none that I ever used!

## Basic Usage Instructions

### On Binder

You can use the `e-ORP` tool interactively on Binder using [this link](https://mybinder.org/v2/gh/dcurrie/e-ORP/HEAD?urlpath=%2Fdoc%2Ftree%2Fe-ORP.ipynb)

Just click the ▶ run button

### On your local device

The advantage of running `e-ORP` on a local device is that your data can be saved and loaded.

The disadvantage is that you need to have a little Python/Jupyter-lab knowledge.

You will need Python 3 installed. Testing was done on Python 3.13.5 on macOS, 
which I installed using Homebrew. You will also need `make` to build `jupyter-lab`
and all the dependencies, and launch it in a virtual environment.

You can run `e-ORP` from a clone of this repo with:

```
make run
```

