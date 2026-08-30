from django.test import SimpleTestCase

from facturacion_electronica.clasificacion_sii import (
    contiene_codigo_estado,
    es_espera_reintento_sii,
    es_falso_rechazo_sii,
    es_glosa_envio_procesado,
    evidencia_rechazo_tributario,
    extraer_segundos_espera,
    extraer_track_id,
)


class ClasificacionSiiTests(SimpleTestCase):
    GLOSA_ESPERA = (
        'Archivo ya fue enviado 2 veces con Trackid 256736750. '
        'Debe esperar 900 segundos antes de reintentar'
    )

    def _dte(self, **kwargs):
        from facturacion_electronica.models import DocumentoTributarioElectronico

        datos = {
            'estado_sii': 'rechazado',
            'glosa_sii': '',
            'error_envio': '',
            'respuesta_sii': '',
            'track_id': '',
        }
        datos.update(kwargs)
        return DocumentoTributarioElectronico(**datos)

    def test_doble_envio_no_es_rechazo_rch(self):
        self.assertTrue(es_espera_reintento_sii(self.GLOSA_ESPERA))
        self.assertFalse(contiene_codigo_estado(self.GLOSA_ESPERA, ('RCH', 'RSC')))
        self.assertFalse(evidencia_rechazo_tributario(self.GLOSA_ESPERA))
        self.assertEqual(extraer_track_id(self.GLOSA_ESPERA), '256736750')
        self.assertEqual(extraer_segundos_espera(self.GLOSA_ESPERA), 900)

    def test_rechazo_real_sigue_detectando_rch(self):
        glosa = 'DTE rechazado. RCH: RUT del receptor invalido'
        self.assertFalse(es_espera_reintento_sii(glosa))
        self.assertTrue(contiene_codigo_estado(glosa, ('RCH', 'RSC')))
        self.assertTrue(evidencia_rechazo_tributario(glosa))

    def test_doble_envio_no_bloquea_emision(self):
        dte = self._dte(glosa_sii=self.GLOSA_ESPERA)
        self.assertTrue(dte.en_espera_reintento_sii())
        self.assertEqual(dte.get_estado_sii_real(), 'enviado')
        self.assertEqual(dte.get_estado_sii_real_display(), 'Pendiente SII')
        self.assertTrue(dte.puede_emitir_documento_tributario)
        self.assertFalse(dte.puede_enviarse_al_sii)

    def test_envio_procesado_no_es_rechazo(self):
        self.assertTrue(es_glosa_envio_procesado('Envio Procesado'))
        self.assertTrue(es_falso_rechazo_sii('Envio Procesado', estado_sii='rechazado', track_id='1'))
        dte = self._dte(glosa_sii='Envio Procesado', track_id='256736750')
        self.assertFalse(dte.en_espera_reintento_sii())
        self.assertEqual(dte.get_estado_sii_real(), 'enviado')
        self.assertEqual(dte.get_estado_sii_real_display(), 'Pendiente SII')
        self.assertFalse(dte.puede_enviarse_al_sii)

    def test_glosa_vacia_con_track_no_es_rechazo(self):
        dte = self._dte(track_id='256736750')
        self.assertEqual(dte.get_estado_sii_real(), 'enviado')
        self.assertFalse(dte.puede_enviarse_al_sii)
        self.assertTrue(dte.puede_emitir_documento_tributario)

    def test_helpers_ignoran_respuesta_sii_deferred(self):
        dte = self._dte(glosa_sii=self.GLOSA_ESPERA)
        dte.get_deferred_fields = lambda: frozenset({'respuesta_sii'})
        self.assertTrue(dte.en_espera_reintento_sii())
        self.assertEqual(dte.get_estado_sii_real(), 'enviado')
        self.assertFalse(dte.puede_enviarse_al_sii)

    def test_corregir_extrae_track_y_pasa_a_enviado(self):
        dte = self._dte(glosa_sii=self.GLOSA_ESPERA)
        self.assertTrue(dte.corregir_falso_rechazo_espera())
        self.assertEqual(dte.estado_sii, 'enviado')
        self.assertEqual(dte.track_id, '256736750')

    def test_corregir_envio_procesado(self):
        dte = self._dte(glosa_sii='Envio Procesado', track_id='111')
        self.assertTrue(dte.corregir_falso_rechazo_espera())
        self.assertEqual(dte.estado_sii, 'enviado')

    def test_rechazo_real_se_mantiene(self):
        dte = self._dte(
            glosa_sii='DTE rechazado. RCH: RUT del receptor invalido',
            track_id='123456',
        )
        self.assertEqual(dte.get_estado_sii_real(), 'rechazado')
        self.assertEqual(dte.get_estado_sii_real_display(), 'Rechazada')
        self.assertFalse(dte.corregir_falso_rechazo_espera())
        self.assertEqual(dte.estado_sii, 'rechazado')

    def test_con_track_nunca_reenvia(self):
        dte = self._dte(estado_sii='enviado', track_id='256736750', glosa_sii=self.GLOSA_ESPERA)
        self.assertFalse(dte.puede_enviarse_al_sii)
        self.assertTrue(dte.tiene_track_sii)
        self.assertTrue(dte.requiere_consulta_estado_sii())

    def test_fau_permite_subir_xml_corregido(self):
        from facturacion_electronica.clasificacion_sii import es_dte_no_recibido_sii

        self.assertTrue(es_dte_no_recibido_sii('FAU', 'DTE No Recibido'))
        dte = self._dte(estado_sii='enviado', track_id='256736750', glosa_sii='FAU DTE No Recibido')
        self.assertTrue(dte.tiene_track_sii)
        self.assertFalse(dte.puede_enviarse_al_sii)
        self.assertTrue(dte.permite_reenvio_xml_corregido)

    def test_con_track_muestra_consulta_aunque_parezca_rechazo(self):
        dte = self._dte(
            estado_sii='rechazado',
            track_id='256736750',
            glosa_sii=self.GLOSA_ESPERA,
        )
        self.assertTrue(dte.tiene_track_sii)
        self.assertFalse(dte.puede_enviarse_al_sii)
        self.assertTrue(dte.requiere_consulta_estado_sii())


class ActecoEmisorTests(SimpleTestCase):
    def test_acteco_cero_es_invalido(self):
        from facturacion_electronica.validacion_envio import (
            errores_emisor_para_dte,
            normalizar_acteco,
            xml_tiene_acteco_invalido,
        )

        self.assertIsNone(normalizar_acteco('0'))
        self.assertIsNone(normalizar_acteco(''))
        self.assertEqual(normalizar_acteco('620200'), '620200')
        self.assertTrue(xml_tiene_acteco_invalido('<Acteco>0</Acteco>'))
        self.assertFalse(xml_tiene_acteco_invalido('<Acteco>620200</Acteco>'))

        class Empresa:
            codigo_actividad_economica = '0'

        errores = errores_emisor_para_dte(Empresa(), '33')
        self.assertTrue(errores)
        self.assertIn('Acteco', errores[0])
        self.assertFalse(errores_emisor_para_dte(Empresa(), '39'))

    def test_factura_con_acteco_valido_pasa(self):
        from facturacion_electronica.validacion_envio import errores_emisor_para_dte

        class Empresa:
            codigo_actividad_economica = '620200'

        self.assertEqual(errores_emisor_para_dte(Empresa(), '33'), [])

    def test_xml_con_prcitem_cero_es_invalido(self):
        from facturacion_electronica.validacion_envio import (
            MENSAJE_PRECIO_CERO,
            xml_tiene_precio_cero,
            validar_precios_items_venta,
        )

        self.assertTrue(xml_tiene_precio_cero('<Detalle><PrcItem>0</PrcItem><MontoItem>1000</MontoItem></Detalle>', '33'))
        self.assertTrue(xml_tiene_precio_cero('<Detalle><PrcItem>1000</PrcItem><MontoItem>0</MontoItem></Detalle>', '39'))
        self.assertFalse(xml_tiene_precio_cero('<Detalle><PrcItem>1000</PrcItem><MontoItem>1000</MontoItem></Detalle>', '33'))
        self.assertTrue(xml_tiene_precio_cero('<Detalle><PrcItem>0</PrcItem><MontoItem>0</MontoItem></Detalle>', '52', '1'))
        self.assertFalse(xml_tiene_precio_cero('<Detalle><MontoItem>0</MontoItem></Detalle>', '52', '5'))

        class Art:
            nombre = 'Cinta'
            precio_venta = '0'
            precio_final = '0'

        class Item:
            cantidad = 1
            precio_unitario = 0
            precio_total = 0
            articulo = Art()

        class Venta:
            class detalles:
                @staticmethod
                def all():
                    return [Item()]
            ventadetalle_set = detalles

        self.assertIn('precio 0', validar_precios_items_venta(Venta(), '33').lower())
        self.assertIn('precio 0', validar_precios_items_venta(Venta(), '52', '1').lower())
        self.assertIsNone(validar_precios_items_venta(Venta(), '52', '5'))
        self.assertIn('folio', MENSAJE_PRECIO_CERO.lower())
