import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import RequestFactory, TransactionTestCase
from django.utils import timezone

from clientes.models import Cliente, ContactoCliente
from empresas.models import Empresa, Sucursal
from .mantenimiento_utils import crear_backup, restaurar_backup
from .respaldo_empresa import (
    SALT, RespaldoError, crear_respaldo, leer_respaldo, restaurar_respaldo,
)


class RespaldosEmpresaTests(TransactionTestCase):
    def setUp(self):
        self.a = Empresa.objects.create(nombre='Empresa A', rut='11.111.111-1')
        self.b = Empresa.objects.create(nombre='Empresa B', rut='22.222.222-2')
        self.ca = Cliente.objects.create(empresa=self.a, nombre='Cliente A', rut='1-9')
        self.cb = Cliente.objects.create(empresa=self.b, nombre='Cliente B', rut='2-7')
        self.contacto = ContactoCliente.objects.create(cliente=self.ca, nombre='Contacto A')
        ContactoCliente.objects.create(cliente=self.cb, nombre='Contacto B')
        self.user = User.objects.create_user(username='admin', is_superuser=True)
        self.factory = RequestFactory()

    def request(self, method='get', data=None):
        request = getattr(self.factory, method)('/', data or {})
        request.user = self.user
        request.empresa = self.a
        request.session = self.client.session
        return request

    def test_exporta_solo_empresa_y_detalles_sin_usuarios(self):
        payload = leer_respaldo(crear_respaldo(self.a), self.a)
        registros = payload['registros']
        self.assertEqual([r['pk'] for r in registros if r['model'] == 'clientes.cliente'], [self.ca.pk])
        self.assertEqual([r['pk'] for r in registros if r['model'] == 'clientes.contactocliente'], [self.contacto.pk])
        self.assertFalse(any(r['model'].startswith(('auth.', 'usuarios.', 'sessions.')) for r in registros))

    def test_restaura_faltantes_actualiza_y_conserva_historia_posterior(self):
        archivo = crear_respaldo(self.a)
        fecha = self.contacto.fecha_creacion
        pk = self.contacto.pk
        self.contacto.delete()
        Cliente.objects.filter(pk=self.ca.pk).update(nombre='Cambio')
        nuevo = Cliente.objects.create(empresa=self.a, nombre='Posterior', rut='3-5')
        restaurar_respaldo(archivo, self.a)
        self.ca.refresh_from_db()
        self.cb.refresh_from_db()
        self.assertEqual(self.ca.nombre, 'Cliente A')
        self.assertEqual(self.cb.nombre, 'Cliente B')
        self.assertEqual(ContactoCliente.objects.get(pk=pk).fecha_creacion, fecha)
        self.assertTrue(Cliente.objects.filter(pk=nuevo.pk).exists())
        # Repetir la recuperación no duplica los registros.
        restaurar_respaldo(archivo, self.a)
        self.assertEqual(ContactoCliente.objects.filter(cliente=self.ca).count(), 1)

    def test_rechaza_otra_empresa(self):
        with self.assertRaisesMessage(RespaldoError, 'otra empresa'):
            restaurar_respaldo(crear_respaldo(self.a), self.b)

    def test_respalda_con_observaciones_sin_copiar_registros_ajenos(self):
        from ventas.models import Venta
        Venta.objects.bulk_create([Venta(empresa=self.a, cliente=self.cb,
                                        numero_venta='CRUCE', total=0)])
        archivo = crear_respaldo(self.a)
        payload = leer_respaldo(archivo, self.a)
        self.assertTrue(payload['advertencias'])
        self.assertNotIn(self.cb.pk, [r['pk'] for r in payload['registros'] if r['model'] == 'clientes.cliente'])
        with self.assertRaisesMessage(RespaldoError, 'Relación incompleta'):
            restaurar_respaldo(archivo, self.a)

    def test_restaura_relaciones_multiples_de_documentos(self):
        from facturacion_electronica.models import ArchivoCAF, DocumentoTributarioElectronico, EnvioDTE
        sucursal = Sucursal.objects.create(empresa=self.a, codigo='TEST', nombre='Principal',
                                           horario_apertura='09:00', horario_cierre='18:00')
        caf = ArchivoCAF(empresa=self.a, sucursal=sucursal, tipo_documento='33',
                         folio_desde=1, folio_hasta=10, cantidad_folios=10,
                         folio_actual=1, fecha_autorizacion=timezone.now().date())
        ArchivoCAF.objects.bulk_create([caf])
        dte = DocumentoTributarioElectronico(empresa=self.a, caf_utilizado=caf,
                 tipo_dte='33', folio=1, fecha_emision=timezone.now().date(),
                 monto_neto=100, monto_iva=19, monto_total=119)
        DocumentoTributarioElectronico.objects.bulk_create([dte])
        envio = EnvioDTE.objects.create(empresa=self.a, usuario=self.user,
                                       cantidad_documentos=1, fecha_envio=timezone.now())
        envio.documentos.add(dte)
        archivo = crear_respaldo(self.a)
        envio.documentos.clear()
        restaurar_respaldo(archivo, self.a)
        self.assertEqual(list(envio.documentos.values_list('pk', flat=True)), [dte.pk])

    def test_rechaza_archivo_alterado_y_sql(self):
        archivo = json.loads(crear_respaldo(self.a))
        archivo['respaldo_firmado'] += 'alterado'
        for contenido in [json.dumps(archivo).encode(), b'DROP TABLE clientes_cliente;', b'[]']:
            with self.assertRaises(RespaldoError):
                restaurar_respaldo(contenido, self.a)

    def test_rechaza_identificador_reasignado_a_otra_empresa(self):
        archivo = crear_respaldo(self.a)
        Cliente.objects.filter(pk=self.ca.pk).update(empresa=self.b)
        with self.assertRaisesMessage(RespaldoError, 'otra empresa'):
            restaurar_respaldo(archivo, self.a)
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.empresa_id, self.b.pk)

    def test_rechaza_relacion_cruzada_incluso_con_firma_valida(self):
        payload = leer_respaldo(crear_respaldo(self.a), self.a)
        contacto = next(r for r in payload['registros'] if r['model'] == 'clientes.contactocliente')
        contacto['fields']['cliente'] = self.cb.pk
        archivo = json.dumps({'respaldo_firmado': signing.dumps(payload, salt=SALT)}).encode()
        with self.assertRaisesMessage(RespaldoError, 'Relación incompleta'):
            restaurar_respaldo(archivo, self.a)

    def test_error_revierte_todas_las_escrituras(self):
        archivo = crear_respaldo(self.a)
        Cliente.objects.filter(pk=self.ca.pk).update(nombre='Cambio')
        with patch('utilidades.respaldo_empresa.connection.check_constraints', side_effect=IntegrityError('fallo')):
            with self.assertRaises(IntegrityError):
                restaurar_respaldo(archivo, self.a)
        self.ca.refresh_from_db()
        self.assertEqual(self.ca.nombre, 'Cambio')

    def test_exige_administrador_y_post_para_restaurar(self):
        self.user.is_superuser = False
        self.assertEqual(crear_backup(self.request()).status_code, 403)
        self.assertEqual(restaurar_backup(self.request('post')).status_code, 403)
        self.user.is_superuser = True
        self.assertEqual(restaurar_backup(self.request()).status_code, 405)

    def test_detecta_cambio_de_empresa_en_pagina(self):
        self.assertEqual(crear_backup(self.request(data={'empresa_id': self.b.pk})).status_code, 400)
        response = restaurar_backup(self.request('post', {'empresa_id': self.b.pk}))
        self.assertEqual(response.status_code, 400)

    def test_descarga_y_restaura_desde_vistas(self):
        response = crear_backup(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertIn('.json', response['Content-Disposition'])
        upload = SimpleUploadedFile('respaldo.json', response.content, content_type='application/json')
        response = restaurar_backup(self.request('post', {'empresa_id': self.a.pk, 'archivo': upload}))
        self.assertEqual(response.status_code, 200, response.content)
