/**
 * @fileoverview 图片处理工具模块
 * @description 提供图片校验、压缩、格式转换等功能的工具类
 *              适用于校园垃圾分类SPA前端图片上传前的预处理场景
 * @module utils/image
 */

/**
 * 支持的图片格式白名单（MIME Type）
 * @constant {string[]}
 */
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

/** 单文件最大允许大小：10MB */
const MAX_FILE_SIZE = 10 * 1024 * 1024;

/** 压缩时最大边长限制（像素） */
const MAX_DIMENSION = 1280;

/** JPEG压缩质量递减序列 */
const QUALITY_STEPS = [0.85, 0.7, 0.5, 0.3];

/**
 * 图片处理器类
 * @class ImageProcessor
 * @description 封装图片校验、压缩、缩略图生成等静态方法，
 *              所有方法均为异步或同步操作，无内部状态依赖
 *
 * @example
 * import { ImageProcessor } from './utils/image.js';
 *
 * // 校验文件
 * const result = ImageProcessor.validate(file);
 * if (!result.valid) {
 *   console.error(result.error);
 * }
 *
 * // 压缩图片
 * const blob = await ImageProcessor.compress(file, 2048);
 */
export class ImageProcessor {

  /**
   * 校验图片文件的格式和大小
   *
   * @static
   * @param {File} file - 待校验的文件对象（来自input[type=file]）
   * @returns {{ valid: boolean, error?: string }} 校验结果对象：
   *   - valid: 是否通过校验
   *   - error: 未通过时的错误提示信息
   *
   * @description 校验规则：
   *   1. 格式仅支持 JPEG/PNG/WebP/GIF
   *   2. 单文件大小不超过10MB，超出则提示需先压缩
   *
   * @example
   * const { valid, error } = ImageProcessor.validate(file);
   * if (!valid) showToast(error, 'error');
   */
  static validate(file) {
    // 格式校验：检查MIME类型是否在白名单内
    if (!ALLOWED_TYPES.includes(file.type)) {
      return {
        valid: false,
        error: `不支持的图片格式：${file.type}，请选择 JPG/PNG/WebP/GIF 格式的图片`
      };
    }

    // 大小校验：超过10MB提示需压缩
    if (file.size > MAX_FILE_SIZE) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      return {
        valid: false,
        error: `图片过大（${sizeMB}MB），最大支持10MB，请先压缩后再上传`
      };
    }

    return { valid: true };
  }

  /**
   * 使用Canvas压缩图片
   *
   * @static
   * @async
   * @param {File} file - 待压缩的原始图片文件
   * @param {number} [maxSizeKB=2048] - 压缩目标大小上限（KB），默认2MB
   * @returns {Promise<Blob>} 压缩后的Blob对象（JPEG格式）
   * @throws {Error} 图片加载失败或压缩过程异常时抛出错误
   *
   * @description 核心算法流程：
   *   1. 创建Image对象并通过Object URL加载原图
   *   2. 计算缩放比例：保持宽高比，最长边不超过1280px
   *   3. 创建Canvas并绘制缩放后的图像
   *   4. 通过toBlob逐步降低quality参数尝试压缩（0.85→0.7→0.5→0.3）
   *   5. 每次检测输出大小，达到目标即返回当前结果
   *   6. 输出统一为JPEG格式以获得更好的压缩率
   *   7. 若原图已小于目标大小则直接返回原文件的Blob副本
   *
   * @example
   * try {
   *   const compressed = await ImageProcessor.compress(file, 1024);
   *   console.log(`压缩后大小: ${compressed.size} bytes`);
   * } catch (err) {
   *   console.error('压缩失败:', err.message);
   * }
   */
  static async compress(file, maxSizeKB = 2048) {
    const targetBytes = maxSizeKB * 1024;

    // 快速路径：原图已满足大小要求，直接返回Blob副本
    if (file.size <= targetBytes) {
      return file.slice(0, file.size, file.type);
    }

    return new Promise((resolve, reject) => {
      const img = new Image();
      const objectURL = URL.createObjectURL(file);

      img.onload = () => {
        try {
          // 计算缩放尺寸：保持宽高比，最长边不超过MAX_DIMENSION
          let { width, height } = img;
          const ratio = Math.min(MAX_DIMENSION / width, MAX_DIMENSION / height, 1);

          // 按比例计算最终尺寸（取整避免亚像素问题）
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);

          // 创建离屏Canvas用于绘制和导出
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');

          // 绘制缩放后的图像到Canvas
          ctx.drawImage(img, 0, 0, width, height);

          // 清理Object URL释放内存
          URL.revokeObjectURL(objectURL);

          // 逐步降低质量进行压缩尝试
          let currentStep = 0;

          const attemptCompress = () => {
            if (currentStep >= QUALITY_STEPS.length) {
              // 所有质量等级都已尝试完毕，使用最低质量的结果
              canvas.toBlob(
                (blob) => resolve(blob),
                'image/jpeg',
                QUALITY_STEPS[QUALITY_STEPS.length - 1]
              );
              return;
            }

            const quality = QUALITY_STEPS[currentStep];
            canvas.toBlob(
              (blob) => {
                // 当前质量下输出已达标，直接返回
                if (blob && blob.size <= targetBytes) {
                  resolve(blob);
                  return;
                }
                // 未达标则尝试下一级更低的质量
                currentStep++;
                attemptCompress();
              },
              'image/jpeg',
              quality
            );
          };

          // 启动压缩尝试流程
          attemptCompress();

        } catch (error) {
          URL.revokeObjectURL(objectURL);
          reject(new Error(`图片压缩处理异常: ${error.message}`));
        }
      };

      // 图片加载失败处理
      img.onerror = () => {
        URL.revokeObjectURL(objectURL);
        reject(new Error('图片文件加载失败，可能文件已损坏'));
      };

      // 触发图片加载
      img.src = objectURL;
    });
  }

  /**
   * 将Blob对象转换为Base64 DataURL字符串
   *
   * @static
   * @async
   * @param {Blob} blob - 待转换的Blob对象
   * @returns {Promise<string>} 完整的DataURL字符串（含 data:image/jpeg;base64, 前缀）
   * @throws {Error} 文件读取失败时抛出错误
   *
   * @description 使用FileReader API读取Blob内容并以Base64编码输出，
   *              结果可直接赋值给img.src或用于API传输。
   *              典型输出格式：data:image/jpeg;base64,/9j/4AAQ...
   *
   * @example
   * const base64 = await ImageProcessor.toBase64(compressedBlob);
   * document.getElementById('preview').src = base64;
   */
  static toBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        // FileReader.result即为完整的DataURL字符串
        resolve(reader.result);
      };

      reader.onerror = () => {
        reject(new Error('Base64转换失败：文件读取异常'));
      };

      // 以DataURL格式读取Blob内容
      reader.readAsDataURL(blob);
    });
  }

  /**
   * 生成图片缩略图的DataURL字符串
   *
   * @static
   * @async
   * @param {File} file - 原始图片文件
   * @param {number} [maxDimension=200] - 缩略图最大边长（像素），默认200px
   * @returns {Promise<string>} 缩略图JPEG格式的Base64 DataURL
   * @throws {Error} 图片加载失败时抛出错误
   *
   * @description 用于历史记录列表中的预览图展示。
   *              处理流程：
   *              1. 加载原图并按比例缩放到maxDimension以内
   *              2. 固定使用JPEG格式+0.6质量输出（兼顾体积与清晰度）
   *              3. 返回Base64字符串便于直接嵌入img标签
   *
   * @example
   * // 为识别记录生成缩略图
   * const thumb = await ImageProcessor.toThumbnail(file, 150);
   * record.thumbnail = thumb; // 存入历史记录
   */
  static toThumbnail(file, maxDimension = 200) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const objectURL = URL.createObjectURL(file);

      img.onload = () => {
        try {
          // 等比缩放：最长边不超过maxDimension
          let { width, height } = img;
          const ratio = Math.min(maxDimension / width, maxDimension / height, 1);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);

          // 创建Canvas并绘制缩略图
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);

          // 清理资源
          URL.revokeObjectURL(objectURL);

          // 以固定质量和格式导出为DataURL
          const dataURL = canvas.toDataURL('image/jpeg', 0.6);
          resolve(dataURL);

        } catch (error) {
          URL.revokeObjectURL(objectURL);
          reject(new Error(`缩略图生成失败: ${error.message}`));
        }
      };

      img.onerror = () => {
        URL.revokeObjectURL(objectURL);
        reject(new Error('缩略图生成失败：图片加载异常'));
      };

      img.src = objectURL;
    });
  }

  /**
   * 获取文件的元信息摘要
   *
   * @static
   * @param {File} file - 文件对象
   * @returns {{ name: string, size: number, sizeFormatted: string, type: string }}
   *   文件元信息对象，各字段说明：
   *   - name: 原始文件名
   *   - size: 文件大小（字节数）
   *   - sizeFormatted: 人类可读的大小字符串（如 "1.5 MB"、"256 KB"）
   *   - type: MIME类型
   *
   * @description 将文件对象的原始属性整理为结构化数据，
   *              并将字节大小自动格式化为KB/MB可读形式。
   *              适用于上传前信息展示、日志记录等场景。
   *
   * @example
   * const info = ImageProcessor.getFileInfo(file);
   * console.log(`${info.name} (${info.sizeFormatted})`);
   * // 输出: photo.jpg (1.5 MB)
   */
  static getFileInfo(file) {
    /** 将字节数格式化为可读字符串 */
    const formatSize = (bytes) => {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    };

    return {
      name: file.name,
      size: file.size,
      sizeFormatted: formatSize(file.size),
      type: file.type
    };
  }

  /**
   * 绑定拖拽上传事件
   * @param {HTMLElement} dropZone - 拖放区域元素
   */
  bindDropUpload(dropZone) {
    if (!dropZone) return;

    ['dragenter', 'dragover'].forEach(event => {
      dropZone.addEventListener(event, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-active');
      });
    });

    ['dragleave', 'drop'].forEach(event => {
      dropZone.addEventListener(event, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-active');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer?.files;
      if (files?.length > 0) {
        this._handleFile(files[0]);
      }
    });

    console.log('[ImageProcessor] 拖拽上传已绑定');
  }

  /**
   * 绑定粘贴上传事件（Ctrl+V / Cmd+V）
   *
   * 支持从剪贴板直接粘贴图片：
   * - 截图工具截图后 Ctrl+V 粘贴
   * - 从网页/文档复制图片后粘贴
   * - 文件管理器中复制图片文件后粘贴
   *
   * @param {HTMLElement} targetElement - 监听粘贴事件的元素（通常是 document 或 input）
   */
  bindPasteUpload(targetElement = document) {
    if (!targetElement) return;

    targetElement.addEventListener('paste', (e) => {
      // 获取剪贴板中的图片数据
      const items = e.clipboardData?.items;

      if (!items) return;

      // 遍历剪贴板项查找图片
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          e.preventDefault();
          e.stopPropagation();

          const file = items[i].getAsFile();
          if (file) {
            console.log('[ImageProcessor] 粘贴图片:', file.type, file.size);
            this._handleFile(file);

            // 触发粘贴成功回调（用于 UI 反馈）
            this._onPasteSuccess?.(file);
          }
          break;
        }
      }
    }, { passive: false }); // 需要阻止默认行为

    console.log('[ImageProcessor] 粘贴上传已绑定 (Ctrl+V)');
  }

  /**
   * 设置粘贴成功的回调函数
   * @param {Function} callback - 回调函数 (file: File) => void
   */
  onPaste(callback) {
    this._onPasteSuccess = callback;
  }
}
