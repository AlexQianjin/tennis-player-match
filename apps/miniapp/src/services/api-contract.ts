/**
 * Compile-time check that the mini program's calls match the generated OpenAPI.
 * `pnpm gen:api` refreshes `packages/shared`, and the CI contract job typechecks
 * this file against that output. A renamed field, path, or enum fails here.
 *
 * Client `request({ url })` values are relative to `/api/v1` (`TARO_APP_API_BASE_URL`
 * already includes that prefix; the cloud transport prepends it).
 */
import type { components, paths } from '@tennis/shared'
import type { CancelPreview } from './match-actions.ts'
import type { PendingRating } from './offline-queue.ts'
import type { Profile, ProfileInput } from '../stores/auth.ts'
import type { Court } from '../stores/court.ts'
import type { MatchSummary, RecommendFilters, RecommendItem, RecommendPage } from '../stores/recommend.ts'

type Schemas = components['schemas']
type Assert<T extends true> = T
type HasKeys<Client extends object, Api extends object> =
  Exclude<keyof Client, keyof Api> extends never ? true : false
type HasOp<P extends keyof paths, M extends 'get' | 'post' | 'patch'> =
  [paths[P][M]] extends [never | undefined]
    ? false
    : paths[P][M] extends { responses: object }
      ? true
      : false
type JsonBody<Op> = Op extends { requestBody: { content: { 'application/json': infer Body } } }
  ? Body
  : never

type ClientApplication = {
  applicationId: string
  applicant: {
    nickname?: string | null
    ntrp?: number | null
    creditScore: number
    bio?: string | null
    style?: string[]
  }
  status: string
  applyTime: string
  llmScore: number | null
  matchReason: string | null
}

type ClientMyItem = MatchSummary & {
  tab: string
  pendingApplicationCount: number | null
}

type ClientDetail = MatchSummary & {
  participants: { user: MatchSummary['publisher']; role: string; arrived: boolean; rated: boolean }[]
  pendingApplicationCount: number | null
  publisher: MatchSummary['publisher'] & {
    age: number | null
    city: string | null
    style: string[]
    bio: string | null
  }
}

export type ApiContractChecks = [
  Assert<HasOp<'/api/v1/auth/login', 'post'>>,
  Assert<HasOp<'/api/v1/user/profile', 'get'>>,
  Assert<HasOp<'/api/v1/user/profile', 'post'>>,
  Assert<HasOp<'/api/v1/courts', 'get'>>,
  Assert<HasOp<'/api/v1/match/publish', 'post'>>,
  Assert<HasOp<'/api/v1/match/recommend', 'get'>>,
  Assert<HasOp<'/api/v1/match/detail/{request_id}', 'get'>>,
  Assert<HasOp<'/api/v1/match/apply', 'post'>>,
  Assert<HasOp<'/api/v1/match/application/withdraw', 'post'>>,
  Assert<HasOp<'/api/v1/match/applications', 'get'>>,
  Assert<HasOp<'/api/v1/match/handle', 'post'>>,
  Assert<HasOp<'/api/v1/match/cancel/preview', 'get'>>,
  Assert<HasOp<'/api/v1/match/cancel', 'post'>>,
  Assert<HasOp<'/api/v1/match/my', 'get'>>,
  Assert<HasOp<'/api/v1/match/arrive', 'post'>>,
  Assert<HasOp<'/api/v1/match/rate', 'post'>>,
  Assert<ProfileInput extends JsonBody<paths['/api/v1/user/profile']['post']> ? true : false>,
  Assert<PendingRating extends JsonBody<paths['/api/v1/match/rate']['post']> ? true : false>,
  Assert<HasKeys<Profile, Schemas['Profile']>>,
  Assert<HasKeys<Court, Schemas['CourtOut']>>,
  Assert<HasKeys<MatchSummary, Schemas['MatchSummary']>>,
  Assert<HasKeys<RecommendItem, Schemas['RecommendItem']>>,
  Assert<HasKeys<RecommendPage, Schemas['RecommendPage']>>,
  Assert<HasKeys<ClientMyItem, Schemas['MyMatchItem']>>,
  Assert<HasKeys<ClientDetail, Schemas['MatchDetail']>>,
  Assert<HasKeys<ClientApplication, Schemas['ApplicationItem']>>,
  Assert<HasKeys<ClientApplication['applicant'], Schemas['UserPublic']>>,
  Assert<HasKeys<{ isNewUser: boolean; userInfo: Profile }, Schemas['LoginResult']>>,
  Assert<HasKeys<{ myCreditScore: number }, Schemas['RateResult']>>,
  Assert<HasKeys<CancelPreview, Schemas['CancelPreview']>>,
  Assert<HasKeys<{ list: Court[] }, Schemas['CourtList']>>,
  Assert<HasKeys<{ list: ClientApplication[] }, Schemas['ApplicationList']>>,
  Assert<
    (RecommendFilters & {
      city: string
      page: number
      pageSize: number
    }) extends paths['/api/v1/match/recommend']['get']['parameters']['query']
      ? true
      : false
  >,
]

const recommendQuery = {
  city: '武汉',
  page: 1,
  pageSize: 10,
  ntrpMin: 3,
  ntrpMax: 4,
  gender: 'male',
  date: '2026-11-02',
  timeSlot: '14:00-16:00',
  courtId: '1',
} satisfies paths['/api/v1/match/recommend']['get']['parameters']['query']

const myQueries = [
  { tab: 'pending', page: 1, pageSize: 10 },
  { tab: 'confirmed' },
  { tab: 'completed' },
  { tab: 'cancelled' },
  { type: 'published' },
  { type: 'applied' },
  { type: 'matched' },
] satisfies NonNullable<paths['/api/v1/match/my']['get']['parameters']['query']>[]

const publishBody = {
  date: '2026-11-02',
  startTime: '14:00',
  endTime: '16:00',
  courtId: '1',
  matchType: 'doubles',
  slotsNeeded: 2,
  genderPref: 'any',
  expectedNtrpMin: 3,
  expectedNtrpMax: 4,
} satisfies JsonBody<paths['/api/v1/match/publish']['post']>

const applyBody = { requestId: '1' } satisfies JsonBody<paths['/api/v1/match/apply']['post']>
const withdrawBody = { applicationId: '1' } satisfies JsonBody<paths['/api/v1/match/application/withdraw']['post']>
const handleBody = {
  applicationId: '1',
  action: 'agree',
} satisfies JsonBody<paths['/api/v1/match/handle']['post']>
const cancelBody = { requestId: '1' } satisfies JsonBody<paths['/api/v1/match/cancel']['post']>
const arriveBody = { requestId: '1' } satisfies JsonBody<paths['/api/v1/match/arrive']['post']>

export const apiContractSamples = {
  recommendQuery,
  myQueries,
  publishBody,
  applyBody,
  withdrawBody,
  handleBody,
  cancelBody,
  arriveBody,
}
