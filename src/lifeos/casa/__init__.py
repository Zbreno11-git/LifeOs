"""A ponte de casa da voz do estúdio (Sessão H1, D70): roda no laptop de casa do dono.

O aparelho do estúdio (a XIAO ESP32-S3 com o microfone) só fala com esta ponte, pela rede de casa,
por HTTPS com o certificado dela fixado no firmware e um token do aparelho. A ponte:

1. confere o interruptor "Viking voz" do Home Assistant antes de tudo (desligado, ou o HA fora:
   nada sai para a nuvem);
2. manda o áudio ao motor (`/voz/ouvir`) e recebe o texto;
3. tenta o HA primeiro (o agente local dele): o que ele reconhece ("liga a luz do estúdio") ele
   faz, sem o Viking;
4. o resto vai ao turno do Viking (`/voz/responder`), e a resposta volta em voz (`/voz/falar`),
   tocada no alto-falante deste laptop;
5. um envio ou uma limpeza que pede aprovação fica aberto por um minuto: dois toques no botão do
   aparelho mandam o código, que a ponte guardou e nunca falou.

A credencial da ponte é a conta `viking-casa@`, com uma chave cuja metade privada nasceu aqui
(`viking casa --preparar`) e nunca sai daqui; o motor só a deixa entrar nas rotas `/voz/*`.
"""
