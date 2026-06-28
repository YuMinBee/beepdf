# CourseBee v2 Case Study

CourseBee v2는 단일 PDF RAG 도구였던 BeePDF를 여러 강의자료 기반 Course Pack 학습 시스템으로 확장한 프로젝트입니다. 핵심은 PDF 하나를 잘 처리하는 데서 멈추지 않고, 실제 학습자가 복습하는 단위인 여러 차시의 Learning Materials를 하나의 Course Pack으로 묶어 Q&A, Study Kit, Concept Map, Podcast Script, TTS artifact까지 생성하는 것입니다.

![CourseBee v2 Architecture](../images/coursebee-v2-architecture.png)

## Problem

초기 BeePDF는 단일 PDF를 입력으로 받아 텍스트를 추출하고, 질문 답변이나 음성 대본 생성으로 이어지는 흐름에 가까웠습니다. 이 구조는 문서 하나를 처리하기에는 단순하고 명확하지만, 실제 강의 복습 상황에서는 한계가 있었습니다.

예를 들어 NLP 11주차를 복습한다고 하면 학생은 1차시, 2차시, 3차시 자료를 따로 보는 것이 아니라 하나의 학습 흐름으로 이해하고 싶어합니다. 단일 PDF RAG에서는 “BPE와 OOV의 관계”처럼 한 문서 안에서 끝나는 질문은 처리할 수 있지만, 여러 차시에 걸친 개념 연결이나 전체 주차 흐름을 안정적으로 다루기 어렵습니다.

또 다른 문제는 provenance입니다. 여러 자료를 섞어 답변을 만들 때는 단순히 답이 그럴듯한 것보다, 어떤 강의자료의 어떤 page/chunk를 근거로 답했는지 추적할 수 있어야 합니다.

## Design Direction

CourseBee v2는 입력 단위를 개별 PDF가 아니라 Course Pack으로 바꿨습니다.

```text
Learning Materials
-> Course Pack Builder
-> Chunk / Metadata
-> Vector Retrieval + Concept Graph
-> Q&A / Study Kit / Concept Map / Podcast Script / TTS
```

각 chunk는 다음과 같은 source metadata를 유지합니다.

```json
{
  "pack_id": "pack_static_nlp_11week_demo",
  "doc_id": "doc_week11_1",
  "filename": "자연어처리_11주차_1차시.pptx",
  "week": 11,
  "lecture_no": 1,
  "page": 3,
  "chunk_id": "p3_c1"
}
```

이 메타데이터는 Q&A, Study Kit, Concept Map, Podcast Script artifact까지 이어집니다. 덕분에 Course Pack 안에서 여러 문서가 함께 사용되더라도, 답변과 학습 자료의 근거를 추적할 수 있습니다.

## GraphRAG-lite

CourseBee v2의 GraphRAG-lite는 full Microsoft GraphRAG가 아닙니다. 이 프로젝트에서는 Course Pack 내부에서 추출한 concept edge와 evidence chunk를 retrieval에 활용하는 lightweight graph-augmented retrieval로 범위를 제한했습니다.

예를 들어 사용자가 다음 질문을 하면:

```json
{
  "pack_id": "pack_static_nlp_11week_demo",
  "question": "BPE와 OOV는 어떤 관계야?",
  "mode": "local_graph"
}
```

시스템은 질문에서 `BPE`, `OOV` 같은 entity를 찾고, Course Pack concept graph에서 관련 edge를 검색한 뒤, edge에 연결된 evidence chunk를 함께 가져옵니다.

```json
{
  "source": "BPE",
  "target": "OOV",
  "relation": "reduces",
  "evidence": [
    {
      "doc_id": "doc_week11_1",
      "filename": "자연어처리_11주차_1차시.pptx",
      "page": 3,
      "chunk_id": "p3_c1"
    }
  ]
}
```

이 방식은 graph를 단순 시각화 artifact로만 두지 않고, 실제 답변 생성 과정에 retrieval context로 참여시킵니다.

## Staged Podcast Generation

긴 팟캐스트 대본 생성에서는 one-shot prompting만으로 원하는 길이와 자연스러운 대화감을 얻기 어려웠습니다. 모델에 “5분 정도” 또는 “6000자 정도”를 요청해도 실제 출력은 짧아지거나, 질문-답변 목록처럼 딱딱해지는 문제가 있었습니다.

그래서 CourseBee v2에서는 podcast generation을 다음 단계로 분해했습니다.

```text
outline -> scene generation -> repair -> TTS
```

이 접근은 모델에게 한 번에 완성본을 요구하는 대신, 먼저 전체 흐름을 잡고, 섹션별 장면을 생성한 뒤, 마지막에 반복과 형식 문제를 보정합니다. 실제 테스트에서는 단순히 모델 크기를 키우는 것보다 generation workflow를 나누는 쪽이 더 안정적인 결과를 만들었습니다.

## Demo Course Pack

- `pack_id`: `pack_static_nlp_11week_demo`
- Input: NLP 11주차 1~3차시 강의자료
- Output: Q&A, Study Kit, Concept Map, Podcast Script, Edge TTS mp3

원본 강의자료는 저작권 문제로 공개하지 않습니다. 공개 포트폴리오에는 구조, 샘플 payload, 샘플 artifact, 코드만 포함합니다.

생성된 mp3나 대형 output 파일은 기본적으로 `outputs/` 아래의 로컬 데모 산출물로 관리합니다. 공개 가능한 샘플만 필요한 경우 `assets/demo/`에 별도로 배치할 수 있습니다.

## Representative Outputs

### Source-grounded Q&A

```json
{
  "answer": "BPE는 OOV 문제를 줄이기 위해 단어를 통째로 unknown 처리하지 않고 subword 조각으로 나누는 토큰화 방식입니다.",
  "sources": [
    {
      "doc_id": "doc_week11_1",
      "filename": "자연어처리_11주차_1차시.pptx",
      "page": 3,
      "chunk_id": "p3_c1"
    }
  ]
}
```

### Study Kit

```json
{
  "overview": "11주차 Course Pack은 BPE/OOV 문제에서 시작해 RNN, LSTM, CNN이 자연어처리 pipeline 안에서 어떤 역할을 하는지 연결해 설명합니다.",
  "flashcards": [
    {
      "front": "BPE는 OOV 문제를 어떻게 줄이는가?",
      "back": "단어를 subword 조각으로 나누어 처음 보는 단어도 기존 조각의 조합으로 처리하게 한다."
    }
  ],
  "expected_questions": [
    "BPE와 word-level tokenization의 차이는 무엇인가?",
    "RNN/LSTM과 CNN은 텍스트를 보는 방식이 어떻게 다른가?"
  ]
}
```

### Podcast Script

```text
HOST: 오늘은 NLP의 복잡한 용어들이 하나의 퍼즐처럼 연결되어 있다는 걸 알아보는 시간이에요.

GUEST: BPE, OOV, RNN, LSTM, CNN 같은 용어들이 각각 다른 분야처럼 보이지만, 사실은 AI가 텍스트를 읽는 과정에서 서로 연결된 단계를 이루고 있어요.
```

## v1 vs v2

| Area | v1 BeePDF | CourseBee v2 |
| --- | --- | --- |
| Input | Single PDF | Multi-document Course Pack |
| Retrieval | Single-document RAG | Source-grounded Course Pack retrieval |
| Graph | Visualization or absent | Concept edge + evidence chunk based local graph retrieval |
| Generation | One-shot script generation | Staged podcast generation |
| Output | Script/TTS centered | Q&A, Study Kit, Concept Map, Podcast Script, TTS artifact |

## Limitations

- GraphRAG-lite는 full GraphRAG가 아니라 Course Pack 내부 concept graph를 활용하는 lightweight retrieval mode입니다.
- background knowledge를 사용할 경우 lecture source evidence와 명확히 분리해 표시할 필요가 있습니다.
- TTS 재생 시간은 문자 수만으로 정확히 예측하기 어렵기 때문에, 실제 제품에서는 `script -> synthesize -> measure -> adjust` 루프가 필요합니다.
- 공개 레포에는 저작권 이슈가 있는 원본 강의자료를 포함하지 않습니다.

## What This Project Demonstrates

1. Multi-document provenance를 고려한 source-grounded RAG 설계
2. full GraphRAG를 과장하지 않고 필요한 범위에서 구현한 lightweight graph-augmented retrieval
3. LLM의 실제 실패 패턴을 관찰하고 `outline -> scene generation -> repair -> TTS`로 분해한 generation orchestration
