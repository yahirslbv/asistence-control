/* Pase de lista: reglas de las casillas (RF-18) y protección contra el doble clic.
 *
 * Reglas, por alumno:
 *   - «Presente» o «Retardo» marcados bloquean «Ausente» (y con él, «Justificado»).
 *   - «Ausente» marcado bloquea «Presente» y «Retardo».
 *   - «Justificado» solo se puede marcar con «Ausente».
 *
 * Esto solo ayuda a quien captura: el servidor vuelve a comprobar las mismas reglas
 * (services/asistencia.py, estado_de_casillas) y rechaza una combinación inválida.
 * Sin JavaScript el formulario sigue enviándose; solo que sin el bloqueo en pantalla.
 */
(function () {
  'use strict';

  var formulario = document.getElementById('pase-de-lista');
  if (!formulario) { return; }

  function casillasDe(fila) {
    var casillas = {};
    var inputs = fila.querySelectorAll('input[data-casilla]');
    for (var i = 0; i < inputs.length; i++) {
      casillas[inputs[i].getAttribute('data-casilla')] = inputs[i];
    }
    return casillas;
  }

  function aplicarReglas(fila) {
    var c = casillasDe(fila);
    if (!c.presente || !c.retardo || !c.ausente || !c.justificado) { return; }

    var llego = c.presente.checked || c.retardo.checked;
    var falto = c.ausente.checked;

    c.ausente.disabled = llego;
    c.presente.disabled = falto;
    c.retardo.disabled = falto;
    c.justificado.disabled = !falto;

    // Lo que queda bloqueado no puede seguir marcado: así nunca se envía una combinación inválida.
    if (c.ausente.disabled) { c.ausente.checked = false; }
    if (c.justificado.disabled) { c.justificado.checked = false; }
  }

  function aplicarATodas() {
    var filas = formulario.querySelectorAll('.fila-lista');
    for (var i = 0; i < filas.length; i++) { aplicarReglas(filas[i]); }
  }

  // Consulta de un periodo inactivo: todo viene bloqueado desde el servidor y así debe quedarse.
  if (!formulario.classList.contains('solo-lectura')) {
    formulario.addEventListener('change', function (evento) {
      var fila = evento.target.closest ? evento.target.closest('.fila-lista') : null;
      if (fila) { aplicarReglas(fila); }
    });
    aplicarATodas();
    // Al volver con «Atrás» el navegador restaura las casillas: se vuelven a aplicar las reglas.
    window.addEventListener('pageshow', aplicarATodas);
  }

  // Evita el doble clic en «Guardar». Si el envío se repite igual, el servidor no duplica
  // nada: esto solo ahorra el aviso.
  var boton = document.getElementById('guardar');
  if (boton) {
    formulario.addEventListener('submit', function () { boton.disabled = true; });
    window.addEventListener('pageshow', function () { boton.disabled = false; });
  }
})();
