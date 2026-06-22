import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

class CTranslate2Translator:
    """Translates text locally using CTranslate2 and Helsinki-NLP OPUS-MT models."""
    
    def __init__(self, model_dir: str, src_lang: str, tgt_lang: str, device: str = "cpu"):
        """
        Initializes the CTranslate2 translator.
        
        Args:
            model_dir: Specific directory containing model.bin and source.spm
            src_lang: Source language code (e.g., 'ja')
            tgt_lang: Target language code (e.g., 'en')
            device: Computing device, either 'cpu' or 'cuda'
        """
        import ctranslate2
        import sentencepiece as spm

        if not os.path.isdir(model_dir):
            raise FileNotFoundError(f"Model directory '{model_dir}' not found.")

        # Load translator. Helsinki-NLP models converted to CTranslate2 can be run with INT8 on CPU.
        # This reduces memory size and speeds up translation with very minor quality degradation.
        try:
            self._translator = ctranslate2.Translator(
                model_dir,
                device=device,
                compute_type="int8",
                inter_threads=1,
                intra_threads=2
            )
        except ValueError:
            # Fallback to default computation type if int8 is unsupported
            self._translator = ctranslate2.Translator(
                model_dir,
                device=device,
                compute_type="default",
                inter_threads=1,
                intra_threads=2
            )

        # Load SentencePiece models
        self._sp_src = spm.SentencePieceProcessor()
        src_spm_path = os.path.join(model_dir, "source.spm")
        if not os.path.exists(src_spm_path):
            raise FileNotFoundError(f"SentencePiece source model '{src_spm_path}' not found.")
        self._sp_src.load(src_spm_path)

        # Some models use target.spm, others reuse source.spm
        self._sp_tgt = spm.SentencePieceProcessor()
        tgt_spm_path = os.path.join(model_dir, "target.spm")
        if os.path.exists(tgt_spm_path):
            self._sp_tgt.load(tgt_spm_path)
        else:
            self._sp_tgt.load(src_spm_path)

        # Executor to run translations asynchronously on a separate thread
        self._executor = ThreadPoolExecutor(max_workers=1)

    def translate(self, text: str) -> str:
        """
        Synchronously translates a string.
        """
        if not text or not text.strip():
            return ""

        # Tokenize input text
        tokens = self._sp_src.encode(text, out_type=str)
        
        # Append EOS token if not already present (required by Helsinki-NLP OPUS-MT models)
        if tokens and tokens[-1] != "</s>":
            tokens.append("</s>")
        
        # Run CTranslate2 batch translation
        results = self._translator.translate_batch([tokens])
        
        # Detokenize target tokens
        output_tokens = results[0].hypotheses[0]
        # Remove EOS from output tokens if present before decoding (though sp.decode usually handles it)
        if output_tokens and output_tokens[-1] == "</s>":
            output_tokens = output_tokens[:-1]
        translated_text = self._sp_tgt.decode(output_tokens)
        return translated_text

    async def translate_async(self, text: str) -> str:
        """
        Asynchronously translates text by running it on a thread pool executor.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.translate, text)

    def close(self) -> None:
        """Cleans up executor resources."""
        self._executor.shutdown(wait=True)


class MockTranslator:
    """Fallback translator that just echoes text with [MOCK] prefix. Useful for testing."""
    
    def __init__(self):
        pass

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        return f"[MOCK] {text}"

    async def translate_async(self, text: str) -> str:
        return self.translate(text)

    def close(self) -> None:
        pass
