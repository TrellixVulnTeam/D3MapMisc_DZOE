

import numpy as np
import os
import sys

# This is needed since the notebook is stored in the object_detection folder.
sys.path.append("..")

import tensorflow as tf
import time
import copy

from tensorflow.core.framework import graph_pb2
from utils import label_map_util
from utils import visualization_utils as vis_util
from matplotlib import pyplot as plt
from PIL import Image


def _node_name(n):
  if n.startswith("^"):
    return n[1:]
  else:
    return n.split(":")[0]


input_graph = tf.Graph()
with tf.Session(graph=input_graph):
    score = tf.placeholder(tf.float32, shape=(None, 1917, 90), name="Postprocessor/convert_scores")
    expand = tf.placeholder(tf.float32, shape=(None, 1917, 1, 4), name="Postprocessor/ExpandDims_1")
    for node in input_graph.as_graph_def().node:
        if node.name == "Postprocessor/convert_scores":
            score_def = node
        if node.name == "Postprocessor/ExpandDims_1":
            expand_def = node


detection_graph = tf.Graph()
with detection_graph.as_default():
  od_graph_def = tf.GraphDef()
  with tf.gfile.GFile('./ssd_mobilenet_v1_ppn/frozen_inference_graph.pb', 'rb') as fid:
    serialized_graph = fid.read()
    od_graph_def.ParseFromString(serialized_graph)
    dest_nodes = ['Postprocessor/convert_scores','Postprocessor/ExpandDims_1']

    edges = {}
    name_to_node_map = {}
    node_seq = {}
    seq = 0
    for node in od_graph_def.node:
      n = _node_name(node.name)
      name_to_node_map[n] = node
      edges[n] = [_node_name(x) for x in node.input]
      node_seq[n] = seq
      seq += 1

    for d in dest_nodes:
      assert d in name_to_node_map, "%s is not in graph" % d

    nodes_to_keep = set()
    next_to_visit = dest_nodes[:]
    while next_to_visit:
      n = next_to_visit[0]
      del next_to_visit[0]
      if n in nodes_to_keep:
        continue
      nodes_to_keep.add(n)
      next_to_visit += edges[n]

    nodes_to_keep_list = sorted(list(nodes_to_keep), key=lambda n: node_seq[n])

    nodes_to_remove = set()
    for n in node_seq:
      if n in nodes_to_keep_list: continue
      nodes_to_remove.add(n)
    nodes_to_remove_list = sorted(list(nodes_to_remove), key=lambda n: node_seq[n])

    keep = graph_pb2.GraphDef()
    for n in nodes_to_keep_list:
      keep.node.extend([copy.deepcopy(name_to_node_map[n])])

    remove = graph_pb2.GraphDef()
    remove.node.extend([score_def])
    remove.node.extend([expand_def])
    for n in nodes_to_remove_list:
      remove.node.extend([copy.deepcopy(name_to_node_map[n])])

    with tf.device('/gpu:0'):
      tf.import_graph_def(keep, name='')
    with tf.device('/cpu:0'):
      tf.import_graph_def(remove, name='')


NUM_CLASSES = 9
label_map = label_map_util.load_labelmap('training/object-detection.pbtxt')
categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
category_index = label_map_util.create_category_index(categories)


def load_image_into_numpy_array(image):
  (im_width, im_height) = image.size
  return np.array(image.getdata()).reshape(
      (im_height, im_width, 3)).astype(np.uint8)



# For the sake of simplicity we will use only 2 images:
# image1.jpg
# image2.jpg
# If you want to test the code with your images, just add path to the images to the TEST_IMAGE_PATHS.
PATH_TO_TEST_IMAGES_DIR = 'test_images'
TEST_IMAGE_PATHS = [ os.path.join(PATH_TO_TEST_IMAGES_DIR, 'image{}.jpg'.format(i)) for i in range(1, 3) ]

# Size, in inches, of the output images.
IMAGE_SIZE = (12, 8)



with detection_graph.as_default():
  with tf.Session(graph=detection_graph,config=tf.ConfigProto(allow_soft_placement=True)) as sess:
    image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
    score_out = detection_graph.get_tensor_by_name('Postprocessor/convert_scores:0')
    expand_out = detection_graph.get_tensor_by_name('Postprocessor/ExpandDims_1:0')
    score_in = detection_graph.get_tensor_by_name('Postprocessor/convert_scores_1:0')
    expand_in = detection_graph.get_tensor_by_name('Postprocessor/ExpandDims_1_1:0')
    detection_boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
    detection_scores = detection_graph.get_tensor_by_name('detection_scores:0')
    detection_classes = detection_graph.get_tensor_by_name('detection_classes:0')
    num_detections = detection_graph.get_tensor_by_name('num_detections:0')
    i = 0
    for _ in range(10):
      image_path = TEST_IMAGE_PATHS[1]
      i += 1
      image = Image.open(image_path)
      image_np = load_image_into_numpy_array(image)
      image_np_expanded = np.expand_dims(image_np, axis=0)
    
      start_time = time.time()
      (score, expand) = sess.run([score_out, expand_out], feed_dict={image_tensor: image_np_expanded})
      (boxes, scores, classes, num) = sess.run(
            [detection_boxes, detection_scores, detection_classes, num_detections],
            feed_dict={score_in:score, expand_in: expand})
      print ('Iteration {0}: {1} sec'.format(i, time.time() - start_time))

      vis_util.visualize_boxes_and_labels_on_image_array(
        image_np,
       np.squeeze(boxes),
      np.squeeze(classes).astype(np.int32),
      np.squeeze(scores),
      category_index,
      use_normalized_coordinates=True,
      line_thickness=8)

    plt.figure(figsize=IMAGE_SIZE)
    plt.imshow(image_np)
    

