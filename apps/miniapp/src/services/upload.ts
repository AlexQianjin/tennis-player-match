import Taro from 'virtual:taro/api'

function fileId(): string {
  const cryptoRef = globalThis.crypto
  if (cryptoRef && typeof cryptoRef.randomUUID === 'function') {
    return cryptoRef.randomUUID()
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`
}

/**
 * Upload a chooseAvatar temp file and return a cloud fileID.
 * The http/dev transport has no cloud storage, so it stores a synthetic
 * `cloud://dev.local/avatars/<id>.jpg` string. The API accepts that shape
 * when CBR_ENV_ID is unset.
 */
export async function uploadAvatarFile(tempPath: string): Promise<string> {
  if (import.meta.env.TARO_APP_TRANSPORT !== 'cloud') {
    const extension = tempPath.includes('.') ? tempPath.slice(tempPath.lastIndexOf('.')) : '.jpg'
    const suffix = extension.length <= 8 ? extension : '.jpg'
    return `cloud://dev.local/avatars/${fileId()}${suffix}`
  }
  const uploaded = await Taro.cloud.uploadFile({
    cloudPath: `avatars/${fileId()}.jpg`,
    filePath: tempPath,
    config: { env: import.meta.env.TARO_APP_CLOUD_ENV },
  })
  if (!uploaded.fileID) {
    throw new Error('头像上传失败')
  }
  return uploaded.fileID
}
