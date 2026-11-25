import 'dart:async';

import 'package:app/core/config/app_config.dart';
import 'package:app/core/network/sse_parser.dart';
import 'package:dio/dio.dart';
import 'package:injectable/injectable.dart';

/// Chamada `POST /consulta` e leitura do stream SSE.
@lazySingleton
class RagRemoteSource {
  /// Cria a fonte.
  const new(this._dio, this._config);

  final Dio _dio;
  final AppConfig _config;

  /// Abre o stream em [endereco]. Falhas de transporte e status fora de 2xx
  /// saem como [DioException] no próprio stream.
  Stream<MensagemSse> consultar(
    String endereco,
    Map<String, Object?> corpo,
  ) async* {
    final resposta = await _dio.post<ResponseBody>(
      '$endereco/consulta',
      data: corpo,
      options: Options(
        responseType: ResponseType.stream,
        headers: {
          'X-API-Key': _config.clientApiKey,
          'Accept': 'text/event-stream',
        },
      ),
    );
    yield* parseSse(resposta.data!.stream);
  }
}
