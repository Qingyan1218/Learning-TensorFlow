#风格转移

#‘换脸’

#原理：
#生成新的图片
#1.内容与原图接近
#2.风格与要求图片接近
#
#对于CNN
#较深层与内容相关
#较浅层与风格相关

from __future__ import absolute_import, division, print_function, unicode_literals
import tensorflow as tf
import os
# 只显示warnings和errors
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

#下载图片或加载本地图片，加载本地图片也需要给出路径
# content_path = tf.keras.utils.get_file('turtle.jpg',
#                                        'https://storage.googleapis.com/download.tensorflow.org/\
#                                        example_images/Green_Sea_Turtle_grazing_seagrass.jpg')
# style_path = tf.keras.utils.get_file('kandinsky.jpg',
#                                      'https://storage.googleapis.com/download.tensorflow.org/\
#                                      example_images/Vassily_Kandinsky%2C_1913_-_Composition_7.jpg')
content_path='.\\turtle.jpg'
style_path='.\\kindinsky.jpg'

import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.rcParams['figure.figsize'] = (12,12)
mpl.rcParams['axes.grid'] = False

#加载图片，画图演示
contentimg = tf.io.read_file(content_path)
contentimg = tf.image.decode_image(contentimg, channels=3)
contentimg = tf.image.convert_image_dtype(contentimg, tf.float32)
plt.subplot(1, 2, 1)
plt.imshow(contentimg)
contentimg = contentimg[tf.newaxis, :]

styleimg = tf.io.read_file(style_path)
styleimg = tf.image.decode_image(styleimg, channels=3)
styleimg = tf.image.convert_image_dtype(styleimg, tf.float32)
plt.subplot(1, 2, 2)
plt.imshow(styleimg)
styleimg = styleimg[tf.newaxis, :]
plt.show()

#加载vgg模型
vgg = tf.keras.applications.VGG19(include_top=False, weights='imagenet')

for layer in vgg.layers:
    print(layer.name)
  
# 内容层
content_layers = ['block5_conv2'] 

# 风格层
style_layers = ['block1_conv1',
                'block2_conv1',
                'block3_conv1', 
                'block4_conv1', 
                'block5_conv1']
#尝试一下使用不同的风格层和内容层
num_content_layers = len(content_layers)
num_style_layers = len(style_layers)

#建立模型输出中间层
def vgg_layers(layer_names):
    vgg = tf.keras.applications.VGG19(include_top=False, weights='imagenet')
    vgg.trainable = False

    outputs = [vgg.get_layer(name).output for name in layer_names]

    model = tf.keras.Model([vgg.input], outputs)
    return model

#计算风格参数
def gram_matrix(input_tensor):
    result = tf.linalg.einsum('bijc,bijd->bcd', input_tensor, input_tensor)
    input_shape = tf.shape(input_tensor)
    num_locations = tf.cast(input_shape[1]*input_shape[2], tf.float32)
    return result/(num_locations)

#输出风格和内容参数
class StyleContentModel(tf.keras.models.Model):
    def __init__(self, style_layers, content_layers):
        super(StyleContentModel, self).__init__()
        self.vgg =  vgg_layers(style_layers + content_layers)
        self.style_layers = style_layers
        self.content_layers = content_layers
        self.num_style_layers = len(style_layers)
        self.vgg.trainable = False

    def call(self, inputs):
        inputs = inputs*255.0
        preprocessed_input = tf.keras.applications.vgg19.preprocess_input(inputs)
        outputs = self.vgg(preprocessed_input)
        style_outputs, content_outputs = (outputs[:self.num_style_layers],
                                          outputs[self.num_style_layers:])

        style_outputs = [gram_matrix(style_output)
                         for style_output in style_outputs]

        content_dict = {content_name:value
                        for content_name, value
                        in zip(self.content_layers, content_outputs)}

        style_dict = {style_name:value
                      for style_name, value
                      in zip(self.style_layers, style_outputs)}

        return {'content':content_dict, 'style':style_dict}

#提取特征
extractor = StyleContentModel(style_layers, content_layers)

results = extractor(tf.constant(contentimg))

style_results = results['style']

#输出提取到的特征
print('Styles:')

for name, output in sorted(results['style'].items()):
    print("  ", name)
    print("    shape: ", output.numpy().shape)
    print("    min: ", output.numpy().min())
    print("    max: ", output.numpy().max())
    print("    mean: ", output.numpy().mean())
    print()

print("Contents:")
for name, output in sorted(results['content'].items()):
    print("  ", name)
    print("    shape: ", output.numpy().shape)
    print("    min: ", output.numpy().min())
    print("    max: ", output.numpy().max())
    print("    mean: ", output.numpy().mean())
  
#优化
style_targets = extractor(styleimg)['style']
content_targets = extractor(contentimg)['content']

image = tf.Variable(contentimg)

def clip_0_1(image):
    return tf.clip_by_value(image, clip_value_min=0.0, clip_value_max=1.0)

#优化器
opt = tf.optimizers.Adam(learning_rate=0.02, beta_1=0.99, epsilon=1e-1)
#内容和风格用不同的系数
style_weight=1e-2
content_weight=1e4

#loss 函数
def style_content_loss(outputs):
    style_outputs = outputs['style']
    content_outputs = outputs['content']
    style_loss = tf.add_n([tf.reduce_mean((style_outputs[name]-style_targets[name])**2) 
                           for name in style_outputs.keys()])
    style_loss *= style_weight / num_style_layers

    content_loss = tf.add_n([tf.reduce_mean((content_outputs[name]-content_targets[name])**2) 
                             for name in content_outputs.keys()])
    content_loss *= content_weight / num_content_layers
    loss = style_loss + content_loss
    return loss

#更新图片
def train_step(image):
    with tf.GradientTape() as tape:
        outputs = extractor(image)
        loss = style_content_loss(outputs)

    grad = tape.gradient(loss, image)
    opt.apply_gradients([(grad, image)])
    image.assign(clip_0_1(image))

#训练
for i in range(5):
    train_step(image)

#输出对比
plt.subplot(1, 2, 1)
plt.imshow(image.read_value()[0])

contentimg = tf.io.read_file(content_path)
contentimg = tf.image.decode_image(contentimg, channels=3)
contentimg = tf.image.convert_image_dtype(contentimg, tf.float32)
plt.subplot(1, 2, 2)
plt.imshow(contentimg)
contentimg = contentimg[tf.newaxis, :]
plt.show()