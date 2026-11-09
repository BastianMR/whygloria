---
type: "SII Resolución"
title: "Resolución N° 121 (2026)"
description: "SERVICIO DE IMPUESTOS INTERNOS SUBDIRECCIÓN DE ASISTENCIA AL CONTRIBUYENTE OFICINA DE DOCUMENTOS TRIBUTARIOS ELECTRÓNICOS"
tags: [SII, 2026, resolucion]
---

SERVICIO DE IMPUESTOS INTERNOS SUBDIRECCIÓN DE ASISTENCIA AL CONTRIBUYENTE OFICINA DE DOCUMENTOS TRIBUTARIOS ELECTRÓNICOS

IMPLEMENTA NUEVAS VALIDACIONES APLICABLES A LOS ARCHIVOS DE LOS DOCUMENTOS TRIBUTARIOS ELECTRÓNICOS EN LOS PROCESOS DE FACTURACIÓN ELECTRÓNICA.

SANTIAGO, 04 DE SEPTIEMBRE DE 2026

RESOLUCIÓN EXENTA SII N° 121.-

## VISTOS:

Lo dispuesto en el artículo 4 bis del DFL N°7, de 1980 sobre Ley Orgánica del Servicio de Impuestos Internos, en el N° 1, de la letra A, del artículo 6°, y en el N° 1, del artículo 8° Bis, ambos del Código Tributario, contenido en el Decreto Ley N° 830, de 1974; en los N°s. 1 y 2, del artículo 2°, en la letra a) del artículo 9 y en los artículos 37°, 42°, 52°, 54° y 71° todos de la Ley sobre Impuesto a las Ventas y Servicios, contenida en el Decreto Ley N° 825, de 1974; en la Ley N° 19.799, sobre documentos electrónicos, firma electrónica y los servicios de certificación de dicha firma; en la Ley N° 21.131 que estableció la obligación de emitir la guía de despacho en formato electrónico obligatoria; en el decreto supremo N° 55, de 1977, del Ministerio de Hacienda, que contiene el Reglamento de la Ley sobre Impuesto a las Ventas y Servicios, en especial su Título XIII sobre Documentos Tributarios, artículos 69 a 71 bis; en las Resoluciones Exentas SII N° 45, de 2003; N° 61, de 2005; N° 107 y N° 108, de 2005; N° 99, de 2019; N° 36 y N° 75, de 2024; N° 154, de 2025; y,

## CONSIDERANDO:

1º Que, conforme al artículo 4 bis de la Ley Orgánica del Servicio de Impuestos Internos y al inciso final del artículo 17 del Código Tributario, este Servicio se encuentra facultado para relacionarse con los contribuyentes a través de medios electrónicos y autorizar o disponer la obligatoriedad de sistemas tecnológicos que reemplacen los soportes de papel en la documentación tributaria, permitiendo automatizar y mejorar el control de cumplimiento.

2º Que, el sistema de Documentos Tributarios Electrónicos, en adelante "DTE", constituye un pilar fundamental del control tributario moderno en Chile, permitiendo al SII verificar en tiempo real la estructura, integridad, validez de folios, firma electrónica, timbre electrónico (TED) e información sustantiva de cada documento.

3º Que, la Resolución Exenta SII N° 45 de 2003, referida al marco regulatorio original del sistema DTE, establece que tales documentos deben cumplir con las especificaciones de formato XML publicadas por el Servicio, incluyendo validaciones técnicas y de negocio al momento de la recepción.

4º Que, la Resolución Exenta SII N° 99 de 2019 reforzó los requisitos para el transporte de bienes corporales muebles, exigiendo que los DTE sean generados, enviados electrónicamente y recibidos por el SII antes del traslado, lo que implica validaciones previas del documento a nivel de estructura y contenido.

5º Que, la Resolución Exenta SII N° 36 de 2024 introdujo requisitos de claridad, formalidad y explicitación en la descripción de productos y servicios en la sección de Detalle de los DTE, desde el 1 de julio de 2024, lo que requiere validaciones adicionales sobre la calidad y legibilidad de las descripciones en el campo "Nombre del Ítem".

6º Que, la Resolución Exenta SII N° 75 de 2024 establece la información obligatoria que deberán contener las guías de despacho y facturas emitidas por los contribuyentes que realicen actividades de explotación forestal.

7º Que, la Resolución Exenta SII N° 154 de 2025 refuerza e incorpora exigencias sustanciales sobre la trazabilidad de traslados de bienes mediante campos de información en facturas y guías de despacho, incluyendo origen, destino, tipo de traslado, datos del transportista y descripción detallada de bienes, cuya presencia y coherencia en el XML debe ser verificada por el Servicio a través de nuevas validaciones.

8º Que, es necesario reforzar el marco de validaciones XML que el Servicio aplica al recibir los DTE, a fin de asegurar que los documentos cumplan con las exigencias normativas y de sistema, previniendo rechazos posteriores y facilitando el cumplimiento de los contribuyentes a través de validaciones previas.

9º Que, el fortalecimiento de estas validaciones contribuye a mejorar el control tributario, la trazabilidad de traslados, la integridad de la información fiscal, la transparencia en las operaciones y la reducción de riesgos de evasión tributaria.

## RESUELVO:

1° IMPLEMÉNTASE un conjunto de nuevas validaciones técnicas y de negocio sobre los Documentos Tributarios Electrónicos (DTE), de conformidad con las normativas detalladas previamente.

Las validaciones a que se refiere el párrafo anterior abarcan los siguientes aspectos:

- a) Validaciones de Estructura XML y Conformidad con Schema: Verificación de que el archivo XML cumple con el schema XML oficial y schema específico del DTE correspondiente publicadas dentro los Instructivos Técnicos en el sitio web del SII 1 , que forman parte integral de esta resolución.
- b) Las validaciones indicadas serán informadas en el sitio web del SII 2 donde se explicarán de forma detallada las nuevas validaciones a los DTE, además de indicar su respectivo efecto en el envío al SII, las cuales se actualizarán permanentemente.

2° Estas validaciones integran el proceso de recepción de DTE realizado por el Servicio de Impuestos Internos, pudiendo su recepción dar lugar a los siguientes estados de documento:

- a) Aceptado: El DTE cumple con todas las validaciones de estructura, firma, TED, folio, descripción de productos, información de trazabilidad (cuando corresponda), montos e impuestos adicionales.
- b) Aceptado con reparos: El DTE cumple con validaciones críticas, como, por ejemplo, validaciones de schema XML, firma, TED, folio, entre otras, pero presenta inconsistencias menores en información complementaria que deberá ser corregida en documentos posteriores (por ejemplo, inconsistencia en decimales, falta de datos opcionales, etc.).
- c) Rechazado: El DTE incumple con una o más validaciones críticas schema XML, firma electrónica, TED, datos obligatorios de emisor, folio, o futuras instrucciones relativas a trazabilidad, impidiendo su incorporación en las bases del SII.

3° Los contribuyentes emisores de DTE deberán adaptar sus sistemas, tanto a aquellos de desarrollo propio como soluciones de mercado, para dar cumplimiento a dichas especificaciones dentro de los plazos que establezca la instrucción respectiva.

4° El incumplimiento de las obligaciones establecidas en la presente Resolución será sancionado de acuerdo con lo dispuesto en el N° 10 del artículo 97 o en el artículo 109, ambos del Código Tributario, según corresponda.

Lo indicado es sin perjuicio de las sanciones penales que correspondan, si los DTE se emiten como medio para la comisión de alguno de los delitos tipificados en el N° 4, del artículo 97 del Código Tributario.

1 Ruta: www.sii.cl &gt; Home &gt; Ayudas &gt; Otros Temas de Ayuda &gt; Factura electrónica &gt; Sistema de Facturación de Mercado

2 Ruta: www.sii.cl &gt; Home &gt; Servicios online &gt; Factura electrónica &gt; Sistema de facturación de mercado &gt; Más información &gt; Instructivo sobre validaciones de DTE

5° La presente resolución entrará en vigencia a contar de su publicación en extracto en el Diario Oficial, sin perjuicio de que las validaciones se implementen de conformidad con la cronología de fases que se establezca según la letra b) del resolutivo 1° de la presente.

## ANÓTESE, COMUNÍQUESE Y PUBLÍQUESE EN EXTRACTO EN EL DIARIO OFICIAL

## DIRECTOR

CST/CAB/OBA/MBU

## DISTRIBUCIÓN:

- Internet.
- Diario Oficial en extracto.
