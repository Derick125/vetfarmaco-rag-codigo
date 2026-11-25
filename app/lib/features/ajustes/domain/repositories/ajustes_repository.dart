import 'package:app/core/error/failures.dart';
import 'package:app/features/ajustes/domain/saude_backend.dart';
import 'package:app/features/telemetria/domain/condicao_campanha.dart';
import 'package:fpdart/fpdart.dart';

/// Ajustes locais e verificação do back-end (`docs/FRONTEND_SPEC.md` §13,
/// reduzido ao endereço).
abstract interface class AjustesRepository {
  /// Grava o endereço do back-end, que sobrepõe o `--dart-define`.
  Future<Either<Failure, Unit>> salvarEndereco(String endereco);

  /// Chama `GET /health` no [endereco] informado.
  Future<Either<Failure, Unit>> testarBackend(String endereco);

  /// Chama `GET /health` e devolve o que o back-end informa (modelo em uso).
  Future<Either<Failure, SaudeBackend>> consultarSaude(String endereco);

  /// Último modelo que o `/health` informou (guardado a cada resposta
  /// bem-sucedida); `null` se nunca respondeu. Serve às medições feitas sem
  /// rede, quando o `/health` do envio não é alcançável.
  Future<String?> ultimoModeloConhecido();

  /// Condição de rede da campanha escolhida; `naoInformada` se nenhuma.
  Future<CondicaoCampanha> condicaoCampanha();

  /// Grava a condição de rede da campanha.
  Future<Either<Failure, Unit>> salvarCondicaoCampanha(
    CondicaoCampanha condicao,
  );
}
