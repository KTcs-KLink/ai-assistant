import type { FormReference } from './types'
// Requested form types only. No invented official templates, files or application endpoints.
export const formReferences: FormReference[] = [
  {
    id: 'leave',
    title: '휴가신청서',
    category: '휴가·휴직',
    description: '휴가 종류와 기간을 정리하고 필요한 증빙을 확인해요.',
    fields: [
      '신청할 휴가 종류와 기간',
      '잔여 일수와 근무 일정',
      '회사에서 요구하는 증빙·승인 경로',
    ],
  },
  {
    id: 'travel',
    title: '출장신청·사전품의서',
    category: '출장·정산',
    description: '출장 계획과 사전 승인에 필요한 내용을 준비해요.',
    fields: ['출장 목적·일정·방문지', '교통·숙박 계획과 예상 비용', '사전 승인 및 공식 품의 양식'],
  },
  {
    id: 'expense',
    title: '출장비 정산서',
    category: '출장·정산',
    description: '출장 실적과 지출 내역을 모아 정산을 준비해요.',
    fields: ['승인된 출장 정보와 실제 일정', '영수증과 지출 내역', '정산 기준과 공식 회사 양식'],
  },
  {
    id: 'resignation',
    title: '사직원',
    category: '입사·퇴직',
    description: '퇴직 희망 일정과 제출 절차를 확인해요.',
    fields: ['퇴직 희망일과 협의 일정', '사직원 공식 양식과 제출 경로', '인수인계·자산 반납 절차'],
  },
  {
    id: 'handover',
    title: '업무인수인계서',
    category: '입사·퇴직',
    description: '담당 업무와 진행 중인 일을 빠짐없이 정리해요.',
    fields: [
      '담당 업무와 진행 상황',
      '인계 대상자·일정·자료 목록',
      '회사 공식 양식 및 검토 담당자',
    ],
  },
  {
    id: 'retirement',
    title: '퇴직업무 확인서',
    category: '입사·퇴직',
    description: '퇴직 전 확인할 업무와 반납 절차를 점검해요.',
    fields: ['자산 반납과 계정 처리', '정산 및 관련 확인 부서', '공식 퇴직 체크리스트와 승인 경로'],
  },
]
