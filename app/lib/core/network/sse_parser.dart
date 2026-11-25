import 'dart:async';
import 'dart:convert';

/// Mensagem SSE: o par `event`/`data` fechado por uma linha em branco.
class MensagemSse {
  /// Cria a mensagem.
  const new({required this.evento, required this.dados});

  /// Valor de `event:` (padrão `message`).
  final String evento;

  /// Linhas `data:` unidas por `\n`.
  final String dados;
}

/// Converte os bytes de uma resposta `text/event-stream` em [MensagemSse].
///
/// Aceita `\n`, `\r\n` e `\r`, ignora comentários (`: ping` do servidor) e
/// descarta blocos sem `data`.
Stream<MensagemSse> parseSse(Stream<List<int>> bytes) async* {
  var evento = 'message';
  final dados = <String>[];
  var temDados = false;

  await for (final linha
      in bytes
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter())) {
    if (linha.isEmpty) {
      if (temDados) {
        yield MensagemSse(evento: evento, dados: dados.join('\n'));
      }
      evento = 'message';
      dados.clear();
      temDados = false;
      continue;
    }
    if (linha.startsWith(':')) continue;
    final i = linha.indexOf(':');
    final campo = i < 0 ? linha : linha.substring(0, i);
    var valor = i < 0 ? '' : linha.substring(i + 1);
    if (valor.startsWith(' ')) valor = valor.substring(1);
    switch (campo) {
      case 'event':
        evento = valor;
      case 'data':
        dados.add(valor);
        temDados = true;
    }
  }
  // Stream cortado antes da linha em branco final: o bloco incompleto não
  // é entregue — evento pela metade nunca vira resposta.
}
