---
type: "SII Resolución"
title: "Resolución N° 43 (2024)"
description: "SUBDIRECCIÓN DE GESTIÓN ESTRATÉGICA Y ESTUDIOS TRIBUTARIOS GE269961"
tags: [SII, 2024, resolucion]
materia: "Aprueba Modificación de Convenio de Intercambio de Información y Colaboración entre el Instituto Nacional de Propiedad Industrial y el Servicio de Impuestos Internos."
fecha: "2024-04-03"
exenta: true
impuestos: []
formularios: []
regimen: ["no-aplica"]
ref_legal: ["Lo dispuesto en los artículos 1° y 7° letras a), c) y o) de la Ley Orgánica del Servicio de Impuestos Internos, contenida en el artículo Primero del D.F.L N° 7, de Hacienda, de 1980"]
---

## SUBDIRECCIÓN DE GESTIÓN ESTRATÉGICA Y ESTUDIOS TRIBUTARIOS GE269961

MATERIA: Aprueba Modificación de Convenio de Intercambio de Información y Colaboración entre el Instituto Nacional de Propiedad Industrial y el Servicio de Impuestos Internos.

SANTIAGO, 03 DE ABRIL DE 2024

RESOLUCIÓN EX. SII N°43.-

VISTOS: Lo dispuesto en los artículos 1° y 7° letras a), c) y o) de la Ley Orgánica del Servicio de Impuestos Internos, contenida en el artículo Primero del D.F.L. N° 7, de Hacienda, de 1980; Ley N° 19.628, sobre Protección de la Vida Privada; Ley N° 20.575 que establece el Principio de Finalidad en el Tratamiento de Datos Personales; Ley N° 20.285 sobre Acceso a la Información Pública.

## CONSIDERANDO:

1.- Que, corresponde al Servicio de Impuestos Internos la aplicación y fiscalización de todos los impuestos internos actualmente establecidos o que se establecieren, fiscales o de otro carácter en que tenga interés el Fisco y cuyo control no esté especialmente encomendado por ley a una autoridad diferente.

2.- Que, a su vez, el Instituto Nacional de Propiedad Industrial, es un organismo de carácter técnico y jurídico encargado de la administración y atención de los servicios de la propiedad industrial, conforme a lo dispuesto en las leyes sobre la materia, correspondiéndole promover la protección que brinda la propiedad industrial y difundir el acervo tecnológico y la información de que disponga.

3.- Que, en virtud de lo anterior, el Servicio de Impuestos Internos y el Instituto Nacional de Propiedad Industrial, han acordado suscribir la presente Modificación de Convenio de Intercambio de Información y Colaboración entre ambas instituciones firmado con fecha 27 de diciembre de 2016, aprobado por la Resolución Ex. N° 7, de fecha 18 de enero de 2017, del SERVICIO y la Resolución Ex N°193, de fecha 31 de mayo de 2017, de INAPI, y modificado por Addendum de 15 de junio de 2023, aprobado por Resolución SII EX N° 78 de 28 de junio de 2023, a fin de contribuir al logro de una gestión más eficiente de las funciones que sus respectivas normas orgánicas les han asignado..

## RESUELVO:

Apruébese la modificación de convenio de intercambio de información y colaboración entre el Instituto Nacional de Propiedad Industrial y el Servicio de Impuestos Internos, celebrado el 26 de marzo de 2024, cuyo texto es el siguiente:

## ' MODIFICACIÓN A CONVENIO DE COLABORACIÓN ENTRE EL INSTITUTO NACIONAL DE PROPIEDAD INDUSTRIAL Y EL SERVICIO DE IMPUESTOS INTERNOS

En Santiago, a 26 de marzo de 2024, entre el Servicio de Impuestos Internos, RUT 60.803.000-K, en adelante indistintamente denominado el 'SERVICIO', rep resentado por su Director, don Hernán Frigolett Córdova, cédula de identidad N° 6.367.513-K, ambos con domicilio en Teatinos N° 120, Santiago y el Instituto Nacional de Propiedad Industrial, en adelante indistintamente denominada la 'INAPI', RUT 65.999.669 -3, representado por su Directora Nacional doña Loreto Bresky Ruiz, cédula nacional de identidad Nº 10.730.726-5 ambos con domicilio en Avenida Libertador Bernardo O'Higgins N°194, comuna y ciudad de Santiago, se ha convenido la siguiente modificación al Convenio de Colaboración suscrito entre ambas instituciones:

PRIMERO: Con fecha 27 de diciembre de 2016, ambas partes suscribieron un Convenio de Colaboración, en cuya cláusula tercera se señala como objeto de éste, el intercambio de información entre ambos para ser utilizada dentro del marco de sus competencias, a fin de contribuir al logro de una gestión más eficiente de las funciones que sus respectivas misiones les han encargado.

SEGUNDO: En virtud de lo anterior, ambas partes acuerdan modificar el Anexo N°1 del Convenio aludido, en el sentido de eliminar del Anexo N°1, punto 3 Acceso al web service del INAPI para consultas por medio del número de solicitud.

## Alcances:

El sistema que a continuación se describirá, permitirá consultar Marcas por medio de su número de solicitud, este servicio estará habilitado, una vez que se suscriba el convenio de intercambio de información entre el SERVICIO y el INAPI, además de encontrarse restringido a consultar un máximo de 500 solicitudes diarias.

Para probar el servicio Web, se debe utilizar la siguiente dirección URL dónde se encuentra el descriptor del servicio. URL Test: [<u>http://web1.inapi.cl/tramites/Services/wsConsultas.asmx</u>](http://web1.inapi.cl/tramites/Services/wsConsultas.asmx)

## Descripción del proceso Consulta de Marca:

Utilizar el método getMarcaBySolicitud pasando como parámetro un string con el e-mail habilitado, un entero con el número de solicitud de la marca a consultar, y un string (parámetro por referencia)

Como respuesta, el Servicio Web devolverá un String con un XML de la Marca con los siguientes campos:

| **CAMPO** | **DESCRIPCIÖN** |
| --- | --- |
| TipoCategoriaDescripcion | Tipo de marca; ej. 'Marca Comercial' |
| TipoCoberturaDescripcion | Tipo de cobertura; ej. 'Marca de servicio' |
| TipoMarcaDescripcion | Tipo de marca, ej. 'Marca Mixta, sonora, figurativa, etc.' |
| EstadoDescripcion | Estado de la solicitud de marca, ej. 'concedido' |
| NumeroSolicitud | Número de solicitud de la marca, ej. '1000000' |
| NumeroRegistro | Número de registro, ej. '1015269' |
| FechaPresentacion | Fecha de presentación de la solicitud, ej: '27/03/2012' |
| FechaPublicacion | Fecha de publicación en el diario oficial. |
| FechaRegistro | Fecha de concesión del N° de registro |
| Denominacion | Nombre de la marca, ej. 'Nike' |
| Traduccion | No aplica. |
| EtiquetaDescripcion | Descripción de la etiqueta, ej.' ETIQUETA CONSISTENTE EN UNAETIQUETA EN LA QUE APARECE ESCRITA LA PALABRA "OMNI DANZ" EN LETRAS DE IMPRENTA…' |
| Prioridad | No aplica. |
| Rut | Rut Titular |
| Dv | Digito verificador del rut del titular |
| Domicilio | Dirección del titular |
| NomPais | País del titular |
| NomComuna | Nombre de la comuna del titular |
| Email | E-mail del titular |
| Fono | Fono del titular |

TERCERO: La personería de doña Loreto Bresky Ruiz para representar al INAPI, consta en el Decreto Supremo N°69, del día 21 de junio de 2019, del Ministerio de Economía, Fomento y Turismo.

La personería de don Hernán Frigolett Córdova para representar al Servicio de Impuestos Internos, consta en el Decreto Supremo N°446, del día 31 de marzo de 2022, del Ministerio de Hacienda.

LORETO BRESKY RUIZ DIRECTORA NACIONAL INSTITUTO NACIONAL DE PROPIEDAD INDUSTRIAL

ANÓTESE, COMUNÍQUESE Y PUBLÍQUESE.

<unknown>

AMK Distribución - Internet

HERNÁN FRIGOLETT CÓRDOVA DIRECTOR SERVICIO DE IMPUESTOS INTERNOS

<unknown>

DIRECTOR (S)
