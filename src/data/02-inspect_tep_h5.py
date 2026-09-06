import h5py

path = r"D:\TEP_DigitalTwin\data\unzip\TEP\teps.h5"

with h5py.File(path, "r") as f:
    def show(name, obj):
        print(name, type(obj).__name__, getattr(obj, "shape", ""))

    f.visititems(show)

    print("\nROOT ATTRIBUTES")
    for k, v in f.attrs.items():
        print(k, "=", v)