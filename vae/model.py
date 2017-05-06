import os

from utils import *
import tensorflow as tf
import numpy as np

X_SIZE = 784
Z_SIZE = 128
H_1_SIZE = 256


class VariationalAutoEncoder(object):
    def __init__(self, input_size=X_SIZE, code_size=Z_SIZE, ckpt_path='checkpoints'):
        self.is_training = tf.placeholder(tf.bool)
        self.batch_size = tf.placeholder(tf.int32)
        self.input = tf.placeholder(tf.float32, shape=(None, input_size), name='input')
        self.mu, self.log_var = self._encoder(self.input, code_size)
        self.code_size = code_size
        self.code = self._sample_code(self.mu, self.log_var, self.batch_size)
        self.decoder = self._decoder(self.code, input_size)
        self.input_size = input_size
        self.ckpt_path = ckpt_path
        self.loss = self._loss()

    def _encoder(self, input, code_size):
        with tf.name_scope('encoder'):
            out_1_encoder = fc(input, H_1_SIZE, self.is_training, name='out_1')
            mu, self.w_mu, _, _,  self.h2_mu = fc_with_variables(out_1_encoder, code_size, self.is_training, name='mu', act=tf.tanh, w_init=tf.zeros)
            log_var, self.w_var, _, _, self.h2_var = fc_with_variables(out_1_encoder, code_size, self.is_training, name='log_var', act=tf.tanh, w_init=tf.zeros)
            return mu, log_var

    def _decoder(self, code, out_size):
        with tf.name_scope('decoder'):
            out_1_decoder = fc(code, H_1_SIZE, self.is_training, name='out_1')
            out_decoder = fc(out_1_decoder, out_size, self.is_training, tf.nn.sigmoid, name='out')
            return out_decoder

    def _loss(self):
        with tf.name_scope('loss'):
            data_loss = tf.reduce_sum(tf.square(self.input - self.decoder), axis=1)
            kl_loss = 0.5 * tf.reduce_sum(tf.exp(self.log_var) + tf.square(self.mu) - 1. - self.log_var, axis=1)
            return tf.reduce_mean(data_loss + kl_loss, name='loss')

    # def _loss(self):
    #     with tf.name_scope('loss'):
    #         data_loss = tf.reduce_sum(tf.square(self.input - self.decoder), axis=1)
    #         kl_loss = 0.5 * tf.reduce_sum(tf.square(self.mu), axis=1)
    #         return tf.reduce_mean(data_loss + kl_loss, name='loss')

    def _load(self, sess):
        sess.run(tf.global_variables_initializer())
        ckpt = tf.train.get_checkpoint_state(os.path.dirname(self.ckpt_path + '/checkpoint'))
        if ckpt and ckpt.model_checkpoint_path:
            tf.train.Saver().restore(sess, ckpt.model_checkpoint_path)

    def _sample_code(self, mu, log_var, batch_size):
        with tf.name_scope('sample_code'):
            unit_gaussian = tf.random_normal((batch_size, self.code_size), name='unit_gaussian')
            sigma = tf.exp(log_var / 2)
            return mu + sigma * unit_gaussian

    # def _sample_code(self, mu, batch_size):
    #     with tf.name_scope('sample_code'):
    #         unit_gaussian = tf.random_normal((batch_size, self.code_size), name='unit_gaussian')
    #         return tf.add(mu, unit_gaussian)

    def train(self, sess, data, final_step, lr, batch_size, ckpt_step=1):
        global_step = tf.Variable(0, dtype=tf.int32, trainable=False, name='global_step')
        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):
            optimizer = tf.train.AdamOptimizer(learning_rate=lr).minimize(self.loss, global_step=global_step)
        grad_loss = tf.gradients(self.loss, [self.w_mu, self.w_var])
        grad_encoder = tf.gradients([self.mu, self.log_var], [self.h2_mu, self.h2_var])

        self._load(sess)

        prev_loss, d_loss = 0., 0.
        for step in range(global_step.eval(), final_step):
            input_batch, _ = data.next_batch(batch_size)
            # mu, log_var = sess.run([self.mu, self.log_var], feed_dict={self.input: input_batch})
            # code = sess.run(self._sample_code(self.mu, self.log_var), feed_dict={self.input: input_batch, self.is_training: True})
            _, loss, g_loss, g_encoder = sess.run([optimizer, self.loss, grad_loss, grad_encoder],
                                                  feed_dict={self.input: input_batch, self.is_training: True, self.batch_size: batch_size})

            if (step + 1) % ckpt_step == 0:
                if prev_loss:
                    d_loss = (loss / prev_loss - 1)
                prev_loss = loss

                tf.train.Saver().save(sess, self.ckpt_path + '/vae', global_step=step)
                print 'step-{}\td_loss={:2.2f}%\tloss={}'.format(step, d_loss * 100, loss)
                # print 'grad_loss={}, grad_encoder={}'.format(g_loss, g_encoder)

    def test(self, sess, data, visualizer, num=2):
        x, _ = data.next_batch(num)
        for o in x:
            visualizer(o)

        self._load(sess)
        mu, log_var = sess.run([self.mu, self.log_var], feed_dict={self.input: x, self.is_training: False})
        print '<mu>\n{}\n\n<log_var>\n{}'.format(mu, log_var)

        out = sess.run(self.decoder, feed_dict={self.mu: mu, self.log_var: log_var, self.is_training: False})
        for o in out:
            visualizer(o)

    def generate(self, sess, visualizer, num=2):
        self._load(sess)
        mu = tf.zeros(shape=(num, self.code_size), dtype=tf.float32, name='mu')
        log_var = tf.zeros(shape=(num, self.code_size), dtype=tf.float32, name='log_var')
        code = sess.run(self._sample_code(mu, log_var, num))
        print code
        out = sess.run(self.decoder, feed_dict={self.code: code, self.is_training: False})
        for o in out:
            visualizer(o)
