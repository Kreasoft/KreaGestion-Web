import base64

# El XML en base64 del log
xml_base64 = "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iSVNPLTg4NTktMSI/PjxEVEUgdmVyc2lvbj0iMS4wIj4KICA8RG9jdW1lbnRvIElEPSJGNzNUNTIiPgogICAgPEVuY2FiZXphZG8+CiAgICAgIDxJZERvYz4KICAgICAgICA8VGlwb0RURT41MjwvVGlwb0RURT4KICAgICAgICA8Rm9saW8+NzM8L0ZvbGlvPgogICAgICAgIDxGY2hFbWlzPjIwMjUtMTItMzE8L0ZjaEVtaXM+CiAgICAgICAgPEZtYVBhZ28+MTwvRm1hUGFnbz4KICAgICAgICA8SW5kVHJhc2xhZG8+MTwvSW5kVHJhc2xhZG8+CiAgICAgIDwvSWREb2M+CiAgICAgIDxFbWlzb3I+CiAgICAgICAgPFJVVEVtaXNvcj43NzExNzIzOS0zPC9SVVRFbWlzb3I+CiAgICAgICAgPFJ6blNvYz5Tb2NpZWRhZCBJbmZvcm1hdGljYSBLcmVhc29mdCBTcEE8L1J6blNvYz4KICAgICAgICA8R2lyb0VtaXM+RGVzYXJyb2xsbyBkZSBTb2Z0d2FyZTwvR2lyb0VtaXM+CiAgICAgICAgPERpck9yaWdlbj5WaWN0b3IgUGxhemEgTWF5b3JnYSA4ODc8L0Rpck9yaWdlbj4KICAgICAgICA8Q21uYU9yaWdlbj5FbCBCb3NxdWU8L0NtbmFPcmlnZW4+CiAgICAgIDwvRW1pc29yPgogICAgICA8UmVjZXB0b3I+CiAgICAgICAgPFJVVFJlY2VwPjc2NjI2MjMxLTc8L1JVVFJlY2VwPgogICAgICAgIDxSem5Tb2NSZWNlcD5UUkFOUE9SVEVTIEJPUklTIFNBTlpBTkEgRUlSTDwvUnpuU29jUmVjZXA+CiAgICAgICAgPERpclJlY2VwPlNBTlRBIENBVEFMSU5BIDkzNSA8L0RpclJlY2VwPgogICAgICAgIDxDbW5hUmVjZXA+cGFkcmUgbGFzIGNhc2FzPC9DbW5hUmVjZXA+CiAgICAgIDwvUmVjZXB0b3I+CiAgICAgIDxUb3RhbGVzPgogICAgICAgIDxNbnROZXRvPjg4MDA8L01udE5ldG8+CiAgICAgICAgPE1udEV4ZT4wPC9NbnRFeGU+CiAgICAgICAgPFRhc2FJVkE+MTk8L1Rhc2FJVkE+CiAgICAgICAgPElWQT4xNjcyPC9JVkE+CiAgICAgICAgPE1udFRvdGFsPjEwNDcyPC9NbnRUb3RhbD4KICAgICAgPC9Ub3RhbGVzPgogICAgPC9FbmNhYmV6YWRvPgogICAgPERldGFsbGU+CiAgICAgIDxOcm9MaW5EZXQ+MTwvTnJvTGluRGV0PgogICAgICA8Tm1iSXRlbT5BTUFSUkEgQUpVU1RBQkxFIDUgTUVUUk9TPC9ObWJJdGVtPgogICAgICA8RHNjSXRlbT5BTUFSUkEgQUpVU1RBQkxFIDUgTUVUUk9TPC9Ec2NJdGVtPgogICAgICA8UXR5SXRlbT4xLjA8L1F0eUl0ZW0+CiAgICAgIDxVbm1kSXRlbT5VTjwvVW5tZEl0ZW0+CiAgICAgIDxQcmNJdGVtPjM5MDA8L1ByY0l0ZW0+CiAgICAgIDxNb250b0l0ZW0+MzkwMDwvTW9udG9JdGVtPgogICAgPC9EZXRhbGxlPgogICAgPERldGFsbGU+CiAgICAgIDxOcm9MaW5EZXQ+MjwvTnJvTGluRGV0PgogICAgICA8Tm1iSXRlbT5BTUFSUkEgUExBU1RJQ0E8L05tYkl0ZW0+CiAgICAgIDxEc2NJdGVtPkFNQVJSQSBQTEFTVElDQTwvRHNjSXRlbT4KICAgICAgPFF0eUl0ZW0+MS4wPC9RdHlJdGVtPgogICAgICA8VW5tZEl0ZW0+VU48L1VubWRJdGVtPgogICAgICA8UHJjSXRlbT4zOTAwPC9QcmNJdGVtPgogICAgICA8TW9udG9JdGVtPjM5MDA8L01vbnRvSXRlbT4KICAgIDwvRGV0YWxsZT4KICAgIDxEZXRhbGxlPgogICAgICA8TnJvTGluRGV0PjM8L05yb0xpbkRldD4KICAgICAgPE5tYkl0ZW0+QU1BUlJBIFBMQVNUSUNBICg1MCBVTklEQURFUyk8L05tYkl0ZW0+CiAgICAgIDxEc2NJdGVtPkFNQVJSQSBQTEFTVElDQSAoNTAgVU5JREFERVMpPC9Ec2NJdGVtPgogICAgICA8UXR5SXRlbT4xLjA8L1F0eUl0ZW0+CiAgICAgIDxVbm1kSXRlbT5VTjwvVW5tZEl0ZW0+CiAgICAgIDxQcmNJdGVtPjEwMDA8L1ByY0l0ZW0+CiAgICAgIDxNb250b0l0ZW0+MTAwMDwvTW9udG9JdGVtPgogICAgPC9EZXRhbGxlPgogIDwvRG9jdW1lbnRvPgo8L0RURT4="

# Decodificar
xml_decoded = base64.b64decode(xml_base64).decode('ISO-8859-1')

print("=" * 80)
print("XML COMPLETO ENVIADO A DTEBOX:")
print("=" * 80)
print(xml_decoded)

# Comparar con el ejemplo que funciona
print("\n" + "=" * 80)
print("COMPARACIÓN CON EJEMPLO QUE FUNCIONA:")
print("=" * 80)

problemas = []

# Verificar campos faltantes comparando con el ejemplo
if '<CiudadRecep>' not in xml_decoded:
    problemas.append("❌ FALTA <CiudadRecep> en Receptor")
    
if '<Acteco>' not in xml_decoded:
    problemas.append("❌ FALTA <Acteco> en Emisor")

if '<Telefono>' not in xml_decoded:
    problemas.append("⚠️  FALTA <Telefono> en Emisor (opcional pero recomendado)")

if '<CdgVendedor>' not in xml_decoded:
    problemas.append("⚠️  FALTA <CdgVendedor> en Emisor (opcional)")

if '<GiroRecep>' not in xml_decoded:
    problemas.append("⚠️  FALTA <GiroRecep> en Receptor (opcional)")

if '<CdgItem>' not in xml_decoded:
    problemas.append("⚠️  FALTAN <CdgItem> en Detalles (opcional pero recomendado)")

if problemas:
    print("\nPROBLEMAS ENCONTRADOS:")
    for p in problemas:
        print(f"  {p}")
else:
    print("\n✅ No se encontraron problemas obvios")

print("\n" + "=" * 80)
print("ANÁLISIS:")
print("=" * 80)
print("El XML tiene la estructura correcta para IndTraslado, RznSoc y GiroEmis.")
print("El error HTTP 500 puede deberse a:")
print("  1. Campos faltantes que DTEBox requiere")
print("  2. Formato de datos incorrecto en algún campo")
print("  3. Problema con el servidor de DTEBox")
