import request from '../utils/request'

export function getScoreList(params) {
  return request.get('/score/list', { params })
}

export function getMyScore(params) {
  return request.get('/score/my', { params })
}

export function submitExam(data) {
  return request.post('/score/submit', data)
}
