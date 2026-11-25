import 'package:app/core/error/failures.dart';
import 'package:dio/dio.dart';

/// Converte uma [DioException] na [Failure] correspondente
/// (`docs/ARCHITECTURE.md` §4, `docs/FRONTEND_SPEC.md` §15).
Failure falhaDeDio(DioException e) {
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.transformTimeout:
      return const FalhaTempo('O servidor demorou demais para responder.');
    case DioExceptionType.connectionError:
      return const FalhaRede('Sem conexão com o servidor.');
    case DioExceptionType.badResponse:
      return falhaDeStatus(e.response?.statusCode);
    case DioExceptionType.badCertificate:
    case DioExceptionType.cancel:
    case DioExceptionType.unknown:
      return const FalhaRede('Não foi possível falar com o servidor.');
  }
}

/// [Failure] para um status HTTP fora de 2xx.
Failure falhaDeStatus(int? status) {
  if (status == 429) {
    return const FalhaCota(
      'A cota da API foi atingida. Tente em alguns minutos.',
    );
  }
  if (status != null && status >= 500) {
    return const FalhaServidor('O servidor falhou ao processar o pedido.');
  }
  if (status == 401) {
    return const FalhaContrato('Chave do cliente recusada pelo servidor.');
  }
  return FalhaContrato('Resposta inesperada do servidor ($status).');
}
