// 목 모드 전용: 질문에 따라 미리 정해 둔 답변을 돌려준다.
import type { Attachment, Citation } from './types'

export interface ScriptedAnswer {
  searchNote?: string
  content: string
  citations: Citation[]
}

function kb(id: string, label: string, docName: string, section: string, quote?: string): Citation {
  return { id, label, docName, section, quote, source: 'kb' }
}

export function scriptAnswer(question: string, attachments: Attachment[] = []): ScriptedAnswer {
  const q = question.replace(/\s/g, '')

  if (attachments.length > 0) {
    const file = attachments[0]
    const pages = file.pages ?? 28
    return {
      searchNote: `첨부 파일 ${pages}쪽을 읽음`,
      content:
        '3분기 보고서의 핵심 변화는 세 가지입니다.\n\n' +
        '1. 매출은 전 분기 대비 8% 증가했고, 증가분 대부분이 수도권 B2B 계약에서 나왔습니다[[a1]]\n' +
        '2. 신규 고객 수는 줄었지만 기존 고객 재계약률이 91%로 올랐습니다[[a2]]\n' +
        '3. 4분기에는 영남권 영업 인력 2명 충원이 계획되어 있습니다[[a3]]',
      citations: [
        {
          id: 'a1', label: 'p.4', docName: file.name, section: 'p.4', page: 4, source: 'attachment',
          heading: '2. 지역별 매출',
          context: '3분기 전사 매출은 전 분기 대비 8% 증가하였다. 수도권 B2B 신규 계약 4건이 증가분의 약 70%를 차지하였으며, 영남권은 전 분기와 비슷한 수준을 유지하였다.',
          quote: '수도권 B2B 신규 계약 4건이 증가분의 약 70%를 차지',
        },
        {
          id: 'a2', label: 'p.9', docName: file.name, section: 'p.9', page: 9, source: 'attachment',
          heading: '4. 고객 현황',
          context: '신규 고객 수는 전 분기 대비 12% 감소하였으나, 기존 고객 재계약률은 91%로 전 분기(86%) 대비 5%p 상승하였다.',
          quote: '기존 고객 재계약률은 91%로',
        },
        {
          id: 'a3', label: 'p.22', docName: file.name, section: 'p.22', page: 22, source: 'attachment',
          heading: '7. 4분기 계획',
          context: '영남권 시장 대응을 위해 4분기 중 영업 인력 2명을 충원하고, 부산 지역 거점 사무소 운영을 검토한다.',
          quote: '4분기 중 영업 인력 2명을 충원',
        },
      ],
    }
  }

  if (q.includes('연차') || q.includes('이월')) {
    return {
      searchNote: '문서 3건에서 검색함',
      content:
        '네, 미사용 연차는 **최대 5일**까지 다음 해로 이월할 수 있습니다[[c1]]. 이월된 연차는 다음 해 6월 30일까지 사용해야 하며, 기한 내 미사용분은 소멸됩니다[[c2]].\n\n' +
        '단, 연차 사용 촉진 통지를 받은 후 사용하지 않은 연차는 이월 대상에서 제외됩니다[[c1]].',
      citations: [
        kb('c1', '1', '인사규정_v4.2.pdf', '제23조 연차휴가의 이월 · p.14',
          '…미사용 연차휴가는 [5일을 한도로 다음 연도에 이월]할 수 있다. 다만, 사용 촉진 통지 후 미사용분은 제외한다.'),
        kb('c2', '2', '2026 복리후생 안내.docx', '3.2 휴가 · p.6',
          '이월 연차는 익년 6월 30일까지 사용하여야 하며, 기한 경과 시 소멸된다.'),
        kb('c3', '3', '근태관리 FAQ', '사내 위키 · 2026.03 수정'),
      ],
    }
  }

  if (q.includes('경조사')) {
    return {
      searchNote: '문서 2건에서 검색함',
      content:
        '경조사 휴가는 사유에 따라 다릅니다. 본인 결혼은 **5일**, 자녀 결혼은 1일, 배우자 출산은 **10일**입니다[[c1]].\n\n' +
        '부모·배우자 사망 시 5일, 조부모·형제자매 사망 시 3일이 주어지며, 휴가는 유급이고 경조사 발생일로부터 30일 안에 써야 합니다[[c1]]. 경조금 신청은 그룹웨어 > 복리후생 메뉴에서 할 수 있습니다[[c2]].',
      citations: [
        kb('c1', '1', '인사규정_v4.2.pdf', '제25조 경조사 휴가 · p.16',
          '…본인 결혼 5일, 배우자 출산 10일, [부모 및 배우자 사망 5일]을 유급으로 부여한다.'),
        kb('c2', '2', '2026 복리후생 안내.docx', '4.1 경조금 · p.9',
          '경조금은 [그룹웨어 > 복리후생 > 경조금 신청]에서 증빙과 함께 신청한다.'),
      ],
    }
  }

  if (q.includes('법인카드')) {
    return {
      searchNote: '문서 2건에서 검색함',
      content:
        '법인카드 사용 한도는 직급에 따라 **월 100만~300만 원**입니다[[c1]]. 1회 50만 원을 넘는 결제는 사전에 팀장 승인을 받아야 합니다[[c1]].\n\n' +
        '정산은 사용일이 속한 달의 **다음 달 5일까지** 경비 시스템에 영수증을 올리고 사용 목적을 적으면 됩니다. 기한을 넘기면 개인 부담으로 처리될 수 있습니다[[c2]].',
      citations: [
        kb('c1', '1', '법인카드 운영규정.pdf', '제6조 사용 한도 · p.3',
          '법인카드의 월 사용 한도는 [직급별로 100만 원에서 300만 원]으로 한다.'),
        kb('c2', '2', '경비정산 매뉴얼.pdf', '2. 정산 절차 · p.5',
          '사용자는 [익월 5일까지] 증빙을 첨부하여 정산을 완료하여야 한다.'),
      ],
    }
  }

  if (q.includes('재택')) {
    return {
      searchNote: '문서 1건에서 검색함',
      content:
        '재택근무는 **주 2회**까지 신청할 수 있습니다[[c1]].\n\n' +
        '1. 그룹웨어 > 근태 > 재택근무 신청에서 날짜를 고릅니다[[c1]]\n' +
        '2. 전날 18시까지 팀장 승인을 받아야 합니다[[c1]]\n' +
        '3. 재택 당일에는 메신저 상태를 "재택"으로 두고 VPN에 접속해 근무합니다[[c1]]',
      citations: [
        kb('c1', '1', '재택근무 운영지침.pdf', '제4조 신청 및 승인 · p.2',
          '재택근무는 주 2회 이내로 하며, [전일 18시까지 소속 팀장의 승인]을 받아야 한다.'),
      ],
    }
  }

  if (q.includes('출장') || q.includes('여비')) {
    return {
      searchNote: '문서 1건에서 검색함',
      content:
        '국내 출장비는 출장 종료 후 **7일 이내**에 경비 시스템에서 정산합니다[[c1]]. 교통비·숙박비는 영수증을, 일비는 출장 명령서를 근거로 지급합니다[[c1]].',
      citations: [
        kb('c1', '1', '여비규정_2025개정.pdf', '제9조 정산 · p.7',
          '출장자는 출장 종료일로부터 [7일 이내에 여비를 정산]하여야 한다.'),
      ],
    }
  }

  if (q.includes('회의록') || q.includes('요약')) {
    return {
      content: '요약할 파일이 첨부되지 않았습니다. 입력창 아래 **파일 첨부** 버튼으로 회의록을 올린 뒤 다시 물어봐 주세요.',
      citations: [],
    }
  }

  return {
    searchNote: '문서 0건에서 검색함',
    content: '검색 가능한 사내 문서에서 관련 내용을 찾지 못했습니다. 질문을 조금 더 구체적으로 적어 주시거나 담당 부서에 문의해 주세요.',
    citations: [],
  }
}
