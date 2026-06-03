"""Generate sample CSV files to test the validator."""
import csv, random

materials = [
    ("1000001","Bearing Assembly 6205","ROH","01","EA","KG",0.52,0.48,"KG",0.0,"","-","","1000","0001","001","D1","PD",10,5,14.50,"V",1,"USD"),
    ("1000002","Hydraulic Pump 25cc","FERT","02","EA","KG",8.20,7.80,"KG",0.0,"","-","HYD-25","1000","0001","002","D2","MRP",0,0,245.00,"S",1,"USD"),
    ("1000003","Steel Rod 12mm x 3m","ROH","01","M","KG",2.10,2.10,"KG",0.0,"","-","","1000","0001","001","D1","PD",50,20,3.75,"V",1,"USD"),
    ("1000004","Gasket Set Type A","HALB","03","SET","KG",0.30,0.28,"KG",0.0,"","-","GSK-A","1000","0001","003","D3","VB",5,2,28.00,"S",1,"USD"),
    ("1000005","Electric Motor 2.2kW","FERT","04","EA","KG",22.00,20.50,"KG",0.0,"","-","EM-22","1000","0002","004","D4","MRP",0,0,890.00,"S",1,"USD"),
    ("1000006","O-Ring 50x3","ROH","01","EA","KG",0.02,0.02,"KG",0.0,"","-","","1000","0001","001","D1","PD",100,50,0.45,"V",1,"USD"),
    ("1000007","Control Panel 24V","FERT","05","EA","KG",5.40,5.00,"KG",0.0,"","-","CP-24V","1000","0002","005","D5","MRP",0,0,320.00,"S",1,"USD"),
    ("1000008","Coupling Rigid 30mm","ROH","01","EA","KG",1.20,1.15,"KG",0.0,"","-","","1000","0001","001","D1","PD",20,8,12.80,"V",1,"USD"),
    ("1000009","Pressure Sensor 0-10bar","FERT","06","EA","KG",0.80,0.75,"KG",0.0,"","-","PS-10B","1000","0002","006","D6","MRP",0,0,65.00,"S",1,"USD"),
    ("1000010","Aluminium Sheet 2mm","ROH","07","M2","KG",5.40,5.40,"KG",0.0,"","-","","1000","0001","001","D1","PD",30,15,18.20,"V",1,"USD"),
]

src_headers = ["MATNR","MAKTX","MTART","MATKL","MEINS","GEWEI","BRGEW","NTGEW",
               "GEWEI2","VOLUM","VOLEH","BISMT","MFRPN","WERKS","LGORT",
               "EKGRP","DISPO","DISMM","MINBE","EISBE","STPRS","VPRSV","PEINH","WAERS"]

# Source CSV (as-is from transformation)
with open("sample_data/source_materials.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(src_headers)
    for m in materials:
        row = list(m)
        row[0] = str(row[0]).zfill(18)   # SAP zero-pad
        w.writerow(row)

# Target CSV (S/4HANA export) — same data, different column names, minor issues
tgt_headers = ["Material","Material Description","Material Type","Material Group",
               "Base Unit of Measure","Weight Unit","Gross Weight","Net Weight",
               "Weight Unit2","Volume","Volume Unit","Old Material Number",
               "Manufacturer Part Number","Plant","Storage Location",
               "Purchasing Group","MRP Controller","MRP Type","Reorder Point",
               "Safety Stock","Standard Price","Price Control","Price Unit","Currency"]

with open("sample_data/target_s4hana_export.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(tgt_headers)
    for i, m in enumerate(materials):
        row = list(m)
        # Introduce deliberate mismatches to demonstrate the tool:
        if i == 2:   # material 1000003 — wrong gross weight
            row[6] = 2.50
        if i == 5:   # material 1000006 — wrong description
            row[1] = "O-Ring 50x4"
        if i == 8:   # material 1000009 — wrong standard price
            row[20] = 70.00
        w.writerow(row)

print("✅  Sample files created:")
print("    sample_data/source_materials.csv")
print("    sample_data/target_s4hana_export.csv")
