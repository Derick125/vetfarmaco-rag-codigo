import 'dart:convert';

import 'package:app/core/network/sse_parser.dart';
import 'package:flutter_test/flutter_test.dart';

Stream<List<int>> _bytes(List<String> pedacos) =>
    Stream.fromIterable(pedacos.map(utf8.encode));

Future<List<(String, String)>> _ler(List<String> pedacos) async => [
  await for (final m in parseSse(_bytes(pedacos))) (m.evento, m.dados),
];

void main() {
  test('lê eventos separados por linha em branco, com CRLF', () async {
    final r = await _ler([
      'event: recuperacao\r\ndata: {"chunks":3}\r\n\r\n',
      'event: fim\r\ndata: {"a":1}\r\n\r\n',
    ]);
    expect(r, [('recuperacao', '{"chunks":3}'), ('fim', '{"a":1}')]);
  });

  test('junta pedaços cortados no meio da linha e do caractere', () async {
    final bytes = utf8.encode('event: paragrafo\ndata: {"t":"ação"}\n\n');
    // Corta no meio do "ç" (2 bytes em UTF-8).
    final corte = bytes.indexOf(0xC3) + 1;
    final r = [
      await for (final m in parseSse(
        Stream.fromIterable([bytes.sublist(0, corte), bytes.sublist(corte)]),
      ))
        m.dados,
    ];
    expect(r, ['{"t":"ação"}']);
  });

  test('ignora comentários e ping, e multi-linhas de data viram uma', () async {
    final r = await _ler([': ping\n\n', 'data: a\ndata: b\n\n']);
    expect(r, [('message', 'a\nb')]);
  });

  test('bloco sem linha em branco final não é entregue', () async {
    final r = await _ler(['event: fim\ndata: {}\n']);
    expect(r, isEmpty);
  });
}
