#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Davide Truffa <davide@catoblepa.org>

from asn1crypto import cms, x509
import sys
import re

def estrai_certificati(signed_data):
    certs = []
    if 'certificates' in signed_data and signed_data['certificates'] is not None:
        for cert in signed_data['certificates']:
            if cert.name == 'certificate':
                certs.append(cert.chosen)
    return certs

def cerca_certificato_per_serial(cert_list, serial):
    for cert in cert_list:
        if cert.serial_number == serial:
            return cert
    return None

def estrai_nome_cognome(subject):
    cn = subject.native.get('common_name', '')
    gn = subject.native.get('given_name', '')
    sn = subject.native.get('surname', '')
    if gn and sn:
        return f"{gn} {sn}"
    return cn

def mostra_info_firma(signer, cert_list):
    sid = signer['sid']
    serial = None
    issuer = None
    if sid.name == 'issuer_and_serial_number':
        issuer = sid.chosen['issuer']
        serial = sid.chosen['serial_number'].native
    cert = cerca_certificato_per_serial(cert_list, serial)
    if cert:
        subject = cert.subject
        nome_cognome = estrai_nome_cognome(subject)
        serial_number = subject.native.get('serial_number', '') or subject.native.get('dn_qualifier', '')
        not_after = cert['tbs_certificate']['validity']['not_after'].native
        issuer_str = cert.issuer.human_friendly
        print(f"Firmatario: {nome_cognome}")
        print(f"Numero identificativo: {serial_number}")
        print(f"Data di scadenza: {not_after}")
        print(f"Autorità di certificazione: {issuer_str}")
    else:
        print("Certificato non trovato per questa firma.")
    # Mostra anche altri attributi se vuoi
    if 'signed_attrs' in signer and signer['signed_attrs'] is not None:
        for attr in signer['signed_attrs']:
            if attr['type'].native == 'signing_time':
                print(f"Data firma: {attr['values'].native[0]}")

def analizza_busta(data, livello=1):
    try:
        content_info = cms.ContentInfo.load(data)
        if content_info['content_type'].native == 'signed_data':
            signed_data = content_info['content']
            cert_list = estrai_certificati(signed_data)
            signer_infos = signed_data['signer_infos']
            for idx, signer in enumerate(signer_infos, 1):
                print(f"\n--- Firmatario {idx} (Livello busta {livello}) ---")
                mostra_info_firma(signer, cert_list)
            # Cerca dati annidati (content)
            encap_content = signed_data['encap_content_info']['content']
            if encap_content is not None:
                try:
                    analizza_busta(encap_content.native, livello + 1)
                except Exception:
                    pass
    except Exception as e:
        pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python signers.py file.p7m")
    else:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
        analizza_busta(data)
