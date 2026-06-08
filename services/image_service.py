import cv2
import numpy as np

class ImageService:
    @staticmethod
    def otimizar_imagem_nota(imagem_bytes: bytes) -> bytes:
        """
        Aplica filtros de visão computacional (OpenCV) para melhorar o contraste,
        remover sombras e aumentar a nitidez do texto para o OCR do Gemini.
        """
        try:
            # 1. Converte os bytes recebidos para uma matriz de imagem OpenCV
            nparr = np.frombuffer(imagem_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return imagem_bytes  # Retorna a imagem original se a conversão falhar

            # 2. Converte para Escala de Cinza (Essencial para remover ruídos de cores)
            cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 3. Ajuste de Contraste Adaptativo (CLAHE - Contrast Limited Adaptive Histogram Equalization)
            # Excelente para corrigir fotos com iluminação irregular (metade com sombra, metade com luz)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            contraste = clahe.apply(cinza)

            # 4. Filtro de Nitidez (Sharpening Kernel)
            # Torna as bordas das letras pretas mais vivas e definidas contra o fundo
            kernel = np.array([[0, -1, 0], 
                               [-1, 5, -1], 
                               [0, -1, 0]])
            nitido = cv2.filter2D(contraste, -1, kernel)

            # 5. Converte a imagem tratada de volta para bytes (formato JPEG comprimido)
            _, buffer = cv2.imencode(".jpg", nitido, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            return buffer.tobytes()

        except Exception as e:
            print(f"Aviso: Falha no pré-processamento da imagem, usando original. Erro: {e}")
            return imagem_bytes