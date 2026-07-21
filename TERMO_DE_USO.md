# Termo de Uso — Voice Bass

> **English summary (TL;DR):** Voice Bass is a research/educational real-time
> voice-transformation tool released under the MIT License. By using it you agree that:
> (1) you will only train or use another person's voice model **with that person's explicit
> consent**; (2) you will **not** use it for fraud, identity theft, non-consensual deepfakes,
> harassment, scams or disinformation; (3) the software is provided **"as is"**, and the
> author is **not liable** for misuse committed by third parties; (4) RVC voice models are
> **not** shipped with the app — you are responsible for the origin and authorization of any
> model you add; (5) generated audio carries an **AudioSeal watermark** to support
> traceability. The full, authoritative terms are in Portuguese below.

Este Termo de Uso complementa a licença de software (MIT, ver [LICENSE](LICENSE)) e o aviso
de componentes de terceiros ([NOTICE](NOTICE)). Ao baixar, instalar ou usar o Voice Bass,
você declara que leu e concorda com as condições abaixo.

O Voice Bass é um protótipo acadêmico (Trabalho de Conclusão de Curso) de transformação de
voz em tempo real, destinado a fins de pesquisa, estudo e experimentação pessoal.

## 1. Consentimento do titular da voz

- Você só pode treinar, importar ou utilizar um modelo que reproduza a voz de outra pessoa
  **com o consentimento expresso e verificável do titular daquela voz**.
- Quando a voz for de terceiro (não sua), a autorização é **condição obrigatória** de uso:
  sem consentimento, o uso não é permitido.
- Vozes de pessoas públicas, de terceiros sem autorização, ou obtidas de fontes que você não
  tem direito de utilizar estão **fora** do escopo permitido.

## 2. Usos proibidos

É expressamente vedado usar o Voice Bass, no todo ou em parte, para:

- **Fraude** e **falsificação de identidade** (fazer-se passar por outra pessoa);
- **Deepfakes de voz não consensuais**;
- **Assédio**, ameaça, difamação ou constrangimento de qualquer pessoa;
- **Golpes** financeiros, engenharia social ou obtenção indevida de dados e credenciais;
- **Desinformação**, notícias falsas ou manipulação de opinião;
- Qualquer finalidade **ilegal** ou que viole direitos de terceiros (imagem, voz, honra,
  privacidade ou propriedade intelectual).

## 3. Isenção de responsabilidade (as-is)

- O software é fornecido **"no estado em que se encontra" (as is)**, sem garantias de
  qualquer natureza, conforme o disclaimer da licença [MIT](LICENSE).
- O autor **não se responsabiliza** por quaisquer danos, prejuízos ou consequências
  decorrentes de **usos indevidos praticados por terceiros** ou de qualquer uso em desacordo
  com este Termo.
- A responsabilidade pelo uso do software e por suas consequências é **integralmente do
  usuário**.

## 4. Modelos de voz (RVC) são responsabilidade do usuário

- Os modelos de voz RVC (`.pth` / `.index`) **não acompanham** a distribuição do Voice Bass;
  eles são adicionados pelo próprio usuário na pasta `backend/voices/`.
- Você é **inteiramente responsável** pela origem, pela licença e pela **autorização** de
  qualquer modelo que adicionar, incluindo o consentimento do titular da voz (ver seção 1).
- Modelos de terceiros estão sujeitos às licenças e condições de seus autores (ver
  [NOTICE](NOTICE)).

## 5. Marca d'água (AudioSeal)

- Quando disponível, o Voice Bass injeta uma **marca d'água AudioSeal** no áudio gerado.
- Essa marca funciona como um **mecanismo de rastreabilidade**: ajuda a identificar que o
  áudio foi produzido de forma sintética por esta ferramenta.
- **Não** remova, contorne ou adultere a marca d'água com o objetivo de ocultar a origem
  sintética do áudio. Se, por qualquer motivo, o AudioSeal não puder ser carregado, o
  aplicativo segue sem a marca (degradação graciosa) — o que **não** autoriza nenhum dos usos
  vedados na seção 2.

## 6. Aceite

O uso do Voice Bass implica a aceitação integral deste Termo. Se você não concorda com
qualquer condição aqui descrita, **não** utilize o software.

---

_Documento informativo, em linguagem simples, sem finalidade de parecer jurídico.
Última revisão: julho de 2026._
